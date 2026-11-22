/**
 * POST /review logic with Mastra's mock model: no network, no Google key.
 * Run with `npm test` (Node strips the TypeScript types itself).
 */
import assert from 'node:assert/strict';
import { test } from 'node:test';

import { Agent } from '@mastra/core/agent';
import { createMockModel } from '@mastra/core/test-utils/llm-mock';

import { MAX_IMAGE_BYTES, PROMPT, reviewPhoto } from '../src/mastra/review.ts';

const JPEG = Buffer.concat([Buffer.from([0xff, 0xd8, 0xff, 0xe0]), Buffer.alloc(32)]);
const PNG = Buffer.concat([Buffer.from('\x89PNG\r\n\x1a\n', 'latin1'), Buffer.alloc(32)]);

const BLOCKED = {
  is_sidewalk_hazard: true,
  kind: 'snow',
  severity: 'severe',
  blocked: true,
  confidence: 'high',
  accessibility_issue: true,
  description: 'Snowbank covers the whole sidewalk.',
};

type Call = { prompt: unknown };

function agentAnswering(answer: string | Record<string, unknown>, calls: Call[] = []): Agent {
  return new Agent({
    id: 'test-reviewer',
    name: 'Test reviewer',
    instructions: PROMPT,
    model: createMockModel({
      version: 'v2',
      mockText: answer,
      spyGenerate: (props) => calls.push(props),
      spyStream: (props) => calls.push(props),
    }) as never,
  });
}

function body(image: Buffer, mediaType = 'image/jpeg') {
  return { image_base64: image.toString('base64'), media_type: mediaType };
}

test('returns the assessment JSON from the model', async () => {
  const result = await reviewPhoto(agentAnswering(BLOCKED), body(JPEG));
  assert.equal(result.status, 200);
  assert.deepEqual(result.body, BLOCKED);
});

test('sends the image and the prompt to the model', async () => {
  const calls: Call[] = [];
  await reviewPhoto(agentAnswering(BLOCKED, calls), body(PNG, 'image/png'));
  const sent = JSON.stringify(calls);
  assert.ok(sent.includes(PNG.toString('base64')), 'image is sent');
  assert.ok(sent.includes('image/png'), 'media type is sent');
  assert.ok(sent.includes('winter sidewalk hazard report'), 'prompt is sent');
});

test('model output that breaks the schema is a 502', async () => {
  const result = await reviewPhoto(agentAnswering({ ...BLOCKED, kind: 'lava' }), body(JPEG));
  assert.equal(result.status, 502);
});

test('model output that is not JSON is a 502', async () => {
  const result = await reviewPhoto(agentAnswering('I think it is snowy.'), body(JPEG));
  assert.equal(result.status, 502);
});

test('a body without the fields is a 400', async () => {
  const result = await reviewPhoto(agentAnswering(BLOCKED), { image: 'abc' });
  assert.equal(result.status, 400);
  assert.equal(result.body && 'error' in result.body && result.body.error, 'invalid_request');
});

test('invalid base64 is a 400', async () => {
  const result = await reviewPhoto(agentAnswering(BLOCKED), {
    image_base64: 'not base64!',
    media_type: 'image/jpeg',
  });
  assert.equal(result.status, 400);
});

test('an unsupported media type is a 415', async () => {
  const result = await reviewPhoto(agentAnswering(BLOCKED), body(JPEG, 'image/gif'));
  assert.equal(result.status, 415);
});

test('bytes that do not match the media type are a 415', async () => {
  const result = await reviewPhoto(agentAnswering(BLOCKED), body(JPEG, 'image/png'));
  assert.equal(result.status, 415);
});

test('an image over 5 MB is a 413 and never reaches the model', async () => {
  const calls: Call[] = [];
  const tooBig = Buffer.concat([JPEG, Buffer.alloc(MAX_IMAGE_BYTES)]);
  const result = await reviewPhoto(agentAnswering(BLOCKED, calls), body(tooBig));
  assert.equal(result.status, 413);
  assert.equal(calls.length, 0);
});
