// Browser-only helpers: location (read only while the app is open) and photo shrinking.
import { USE_MOCKS, type LatLon } from "./api";
import { AREA_CENTER } from "./modes";

const LOCATION_TIMEOUT_MS = 10_000;
const MAX_PHOTO_DIMENSION = 1600;
const MAX_PHOTO_BYTES = 5 * 1024 * 1024;
const JPEG_QUALITY = 0.85;

export function getLocation(): Promise<LatLon> {
  return new Promise((resolve, reject) => {
    const fail = (message: string) => (USE_MOCKS ? resolve(AREA_CENTER) : reject(new Error(message)));
    if (!("geolocation" in navigator)) return fail("This browser can't share your location.");
    navigator.geolocation.getCurrentPosition(
      (position) => resolve([position.coords.latitude, position.coords.longitude]),
      (error) =>
        fail(
          error.code === error.PERMISSION_DENIED
            ? "Location is off. Allow location for Lumi to report or answer nearby questions."
            : "Couldn't get your location. Try again outside or near a window.",
        ),
      { enableHighAccuracy: true, timeout: LOCATION_TIMEOUT_MS },
    );
  });
}

// Re-encode as JPEG, at most 1600 px on the long side, to stay under the 5 MB limit.
export async function shrinkPhoto(file: File): Promise<Blob> {
  let bitmap: ImageBitmap;
  try {
    bitmap = await createImageBitmap(file);
  } catch {
    throw new Error("That photo format isn't supported. Try a JPEG or PNG.");
  }
  const scale = Math.min(1, MAX_PHOTO_DIMENSION / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  canvas.getContext("2d")?.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();

  const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", JPEG_QUALITY));
  if (!blob) throw new Error("Couldn't process that photo. Try another one.");
  if (blob.size > MAX_PHOTO_BYTES) throw new Error("The photo is too large. Try another photo.");
  return blob;
}
