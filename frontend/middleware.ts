import { clerkMiddleware } from "@clerk/nextjs/server";

// Clerk reads the session on each request. No route is protected here:
// signed-out people can browse; sign-in is only asked for when they report or vote.
export default clerkMiddleware();

export const config = {
  matcher: [
    // Skip Next.js internals and static files.
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
  ],
};
