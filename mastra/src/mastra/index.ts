import { Mastra } from '@mastra/core';
import { registerApiRoute } from '@mastra/core/server';

import { sidewalkReviewer } from './agents/sidewalk-reviewer';
import { MAX_BODY_BYTES, reviewPhoto } from './review';

export const mastra = new Mastra({
  agents: { sidewalkReviewer },
  server: {
    bodySizeLimit: MAX_BODY_BYTES,
    apiRoutes: [
      registerApiRoute('/review', {
        method: 'POST',
        handler: async (c) => {
          const mastra = c.get('mastra');
          let payload: unknown;
          try {
            payload = await c.req.json();
          } catch {
            return c.json({ error: 'invalid_request', message: 'Body must be JSON.' }, 400);
          }
          const result = await reviewPhoto(mastra.getAgent('sidewalkReviewer'), payload);
          if (result.status !== 200) {
            // Log the reason only, never the image.
            mastra.getLogger()?.warn(`POST /review -> ${result.status}: ${result.body.message}`);
          }
          return c.json(result.body, result.status);
        },
      }),
    ],
  },
});
