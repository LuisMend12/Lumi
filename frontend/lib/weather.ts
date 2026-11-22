// Current Boston conditions from the National Weather Service: free, no key, and
// it allows browser requests. Logan Airport (KBOS) is the nearest official station to BU.
const OBSERVATION_URL = "https://api.weather.gov/stations/KBOS/observations/latest";
const ALERTS_URL = "https://api.weather.gov/alerts/active?point=42.3504,-71.106";

export type Conditions = {
  tempF: number | null;
  feelsLikeF: number | null; // wind chill, when it differs from the temperature
  description: string | null; // e.g. "Light Snow"
  alerts: string[]; // e.g. ["Winter Storm Warning"]
};

type Measurement = { value: number | null } | undefined;

function toF(celsius: Measurement): number | null {
  return celsius?.value == null ? null : Math.round((celsius.value * 9) / 5 + 32);
}

async function getJson(url: string): Promise<unknown> {
  const response = await fetch(url, { headers: { Accept: "application/geo+json" } });
  if (!response.ok) throw new Error(`NWS answered ${response.status}`);
  return response.json();
}

function alertEvents(alerts: unknown): string[] {
  const features = (alerts as { features?: { properties?: { event?: string } }[] } | null)?.features ?? [];
  const events = features.map((feature) => feature.properties?.event).filter((event): event is string => Boolean(event));
  return [...new Set(events)];
}

// null when the NWS can't be reached: the banner then simply doesn't show.
export async function fetchConditions(): Promise<Conditions | null> {
  try {
    const [observation, alerts] = await Promise.all([
      getJson(OBSERVATION_URL),
      getJson(ALERTS_URL).catch(() => null), // alerts are a bonus; the observation alone is enough
    ]);
    const props = (observation as { properties?: Record<string, unknown> }).properties ?? {};
    const tempF = toF(props.temperature as Measurement);
    const chillF = toF(props.windChill as Measurement);
    const description = typeof props.textDescription === "string" && props.textDescription ? props.textDescription : null;
    return {
      tempF,
      feelsLikeF: chillF !== null && chillF !== tempF ? chillF : null,
      description,
      alerts: alertEvents(alerts),
    };
  } catch {
    return null;
  }
}
