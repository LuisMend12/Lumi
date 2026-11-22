import { Agent } from '@mastra/core/agent';

import { PROMPT } from '../review';

/**
 * Free-tier Gemini Flash model with image input and structured output.
 * The key comes from GOOGLE_GENERATIVE_AI_API_KEY (or GOOGLE_API_KEY) in mastra/.env.
 */
export const REVIEW_MODEL = 'google/gemini-3.1-flash-lite';

export const sidewalkReviewer = new Agent({
  id: 'sidewalk-reviewer',
  name: 'Sidewalk reviewer',
  description: 'Checks whether a hazard report photo shows a blocked winter sidewalk.',
  instructions: PROMPT,
  model: REVIEW_MODEL,
});
