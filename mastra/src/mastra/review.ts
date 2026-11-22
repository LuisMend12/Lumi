/**
 * Photo review for Lumi hazard reports: request validation, the agent call,
 * and the JSON contract that the Python backend reads.
 *
 * Kept free of relative imports so the tests can load it directly with Node.
 */
import type { Agent } from '@mastra/core/agent';
import { isMastraTimeoutError } from '@mastra/core/loop';
import { z } from 'zod';

/** The prompt the Claude version used (`PROMPT` in backend/app/photo_review.py), unchanged. */
export const PROMPT =
  'You are assessing a photo submitted as a winter sidewalk hazard report in Boston. ' +
  'Judge only what is visible in the photo. If it does not show a sidewalk or walkway, ' +
  "or shows no hazard, set is_sidewalk_hazard to false, kind to 'none' and severity " +
  "to 'none'. 'blocked' means a pedestrian cannot get through at all. " +
  "'accessibility_issue' means walkable on foot but not for a wheelchair, walker, " +
  'or stroller.';

export const SUPPORTED_MEDIA_TYPES = ['image/jpeg', 'image/png', 'image/webp'] as const;
export type MediaType = (typeof SUPPORTED_MEDIA_TYPES)[number];

/** Decoded image size limit, matching MAX_IMAGE_BYTES in the Python backend. */
export const MAX_IMAGE_BYTES = 5 * 1024 * 1024;

/** Room for a 5 MB image as base64 (4/3 larger) plus the JSON around it. */
export const MAX_BODY_BYTES = 8 * 1024 * 1024;

/** The whole model run must finish before the Python client's 20 s timeout. */
export const MODEL_TIMEOUT_MS = 15_000;

/**
 * Same fields and enums as `PhotoAssessment` in backend/app/photo_review.py
 * (backend/tests/test_photo_review.py checks that they still match).
 */
export const photoAssessmentSchema = z.object({
  is_sidewalk_hazard: z.boolean(),
  kind: z.enum(['snow', 'ice', 'slush', 'puddle', 'obstruction', 'none']),
  severity: z.enum(['none', 'minor', 'moderate', 'severe']),
  blocked: z.boolean(),
  confidence: z.enum(['low', 'medium', 'high']),
  accessibility_issue: z.boolean(),
  description: z.string(),
});
export type PhotoAssessment = z.infer<typeof photoAssessmentSchema>;

const reviewRequestSchema = z.object({
  image_base64: z.string().min(1),
  media_type: z.string(),
});

export type ErrorCode =
  | 'invalid_request'
  | 'unsupported_media_type'
  | 'image_too_large'
  | 'model_error'
  | 'invalid_model_output'
  | 'model_timeout';

type ErrorStatus = 400 | 413 | 415 | 502 | 504;

export type ReviewResult =
  | { status: 200; body: PhotoAssessment }
  | { status: ErrorStatus; body: { error: ErrorCode; message: string } };

function failure(status: ErrorStatus, error: ErrorCode, message: string): ReviewResult {
  return { status, body: { error, message } };
}

const BASE64 = /^[A-Za-z0-9+/]*={0,2}$/;

/** Media type from the image's magic bytes, like detect_media_type() in Python. */
export function sniffMediaType(image: Uint8Array): MediaType | null {
  const startsWith = (...bytes: number[]) => bytes.every((b, i) => image[i] === b);
  const ascii = (from: number, to: number) =>
    Buffer.from(image.subarray(from, to)).toString('latin1');
  if (startsWith(0xff, 0xd8, 0xff)) return 'image/jpeg';
  if (startsWith(0x89, 0x50, 0x4e, 0x47)) return 'image/png';
  if (image.length >= 12 && ascii(0, 4) === 'RIFF' && ascii(8, 12) === 'WEBP') return 'image/webp';
  return null;
}

/**
 * Validate a `POST /review` body and ask the agent about the photo.
 * Never throws: every failure becomes a 4xx or 5xx result with a JSON error.
 */
export async function reviewPhoto(agent: Agent, payload: unknown): Promise<ReviewResult> {
  const request = reviewRequestSchema.safeParse(payload);
  if (!request.success) {
    return failure(
      400,
      'invalid_request',
      'Body must be {"image_base64": string, "media_type": string}.',
    );
  }
  const { image_base64: imageBase64, media_type: mediaType } = request.data;

  if (!(SUPPORTED_MEDIA_TYPES as readonly string[]).includes(mediaType)) {
    return failure(
      415,
      'unsupported_media_type',
      `media_type must be one of ${SUPPORTED_MEDIA_TYPES.join(', ')}.`,
    );
  }
  if (imageBase64.length % 4 !== 0 || !BASE64.test(imageBase64)) {
    return failure(400, 'invalid_request', 'image_base64 is not valid base64.');
  }
  const image = Buffer.from(imageBase64, 'base64');
  if (image.length > MAX_IMAGE_BYTES) {
    return failure(
      413,
      'image_too_large',
      `Image is ${image.length} bytes; the limit is ${MAX_IMAGE_BYTES}.`,
    );
  }
  if (sniffMediaType(image) !== mediaType) {
    return failure(415, 'unsupported_media_type', `Image bytes are not ${mediaType}.`);
  }

  let output: unknown;
  try {
    const result = await agent.generate(
      [
        {
          role: 'user',
          content: [
            {
              type: 'image',
              image: `data:${mediaType};base64,${imageBase64}`,
              mimeType: mediaType,
            },
            { type: 'text', text: 'Assess this report photo.' },
          ],
        },
      ],
      {
        structuredOutput: { schema: photoAssessmentSchema },
        modelSettings: { timeout: { totalMs: MODEL_TIMEOUT_MS } },
      },
    );
    output = result.object;
  } catch (error) {
    if (isMastraTimeoutError(error)) {
      return failure(504, 'model_timeout', `The model did not answer within ${MODEL_TIMEOUT_MS} ms.`);
    }
    const name = error instanceof Error ? error.name : typeof error;
    return failure(502, 'model_error', `The model call failed (${name}).`);
  }

  // Mastra validates structured output already. Check again so the contract
  // with the Python backend holds even if that behavior changes.
  const assessment = photoAssessmentSchema.safeParse(output);
  if (!assessment.success) {
    return failure(
      502,
      'invalid_model_output',
      'The model answer did not match the assessment schema.',
    );
  }
  return { status: 200, body: assessment.data };
}
