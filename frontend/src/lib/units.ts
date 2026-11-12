// Unit conversion for the live speed calculator.
// These constants are the SAME exact factors used by pitchvision/speed.py; the
// vitest suite checks both against known values so the two cannot drift apart.
export const DISTANCE_TO_M = { m: 1, ft: 0.3048, yd: 0.9144 } as const
export const TIME_TO_S = { s: 1, ms: 0.001 } as const
export const MS_TO_KMH = 3.6
export const MS_TO_MPH = 3600 / 1609.344

export type DistanceUnit = keyof typeof DISTANCE_TO_M
export type TimeUnit = keyof typeof TIME_TO_S

export interface SpeedResult { distanceM: number; timeS: number; ms: number; kmh: number; mph: number }

/** Average speed over the measured distance. Returns an error string for invalid input. */
export function averageSpeed(distance: number, time: number, du: DistanceUnit, tu: TimeUnit): SpeedResult | string {
  if (!Number.isFinite(distance) || !Number.isFinite(time)) return 'Enter a distance and a time.'
  if (distance <= 0) return 'Distance must be greater than zero.'
  if (time <= 0) return 'Time must be greater than zero.'
  const distanceM = distance * DISTANCE_TO_M[du]
  const timeS = time * TIME_TO_S[tu]
  const ms = distanceM / timeS
  return { distanceM, timeS, ms, kmh: ms * MS_TO_KMH, mph: ms * MS_TO_MPH }
}

export const convertDistance = (v: number, from: DistanceUnit, to: DistanceUnit) => (v * DISTANCE_TO_M[from]) / DISTANCE_TO_M[to]
export const kmhToMph = (kmh: number) => kmh / 1.609344
