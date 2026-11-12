import { describe, expect, it } from 'vitest'
import { averageSpeed, convertDistance, kmhToMph } from './units'

describe('speed calculator (must match pitchvision/speed.py)', () => {
  it('20 m in 0.5 s is 40 m/s, 144 km/h, 89.48 mph', () => {
    const r = averageSpeed(20, 0.5, 'm', 's')
    if (typeof r === 'string') throw new Error(r)
    expect(r.ms).toBeCloseTo(40, 10)
    expect(r.kmh).toBeCloseTo(144, 10)
    expect(r.mph).toBeCloseTo(89.4774, 3)
  })
  it('gives the same speed in any unit', () => {
    const a = averageSpeed(18.9, 0.62, 'm', 's') as any
    const b = averageSpeed(18.9 / 0.3048, 620, 'ft', 'ms') as any
    const c = averageSpeed(18.9 / 0.9144, 0.62, 'yd', 's') as any
    expect(b.kmh).toBeCloseTo(a.kmh, 9)
    expect(c.kmh).toBeCloseTo(a.kmh, 9)
  })
  it('22 yards is 20.1168 m and 66 ft', () => {
    expect(convertDistance(22, 'yd', 'm')).toBeCloseTo(20.1168, 10)
    expect(convertDistance(22, 'yd', 'ft')).toBeCloseTo(66, 10)
  })
  it('rejects zero, negative and missing input', () => {
    expect(typeof averageSpeed(0, 1, 'm', 's')).toBe('string')
    expect(typeof averageSpeed(10, -1, 'm', 's')).toBe('string')
    expect(typeof averageSpeed(NaN, 1, 'm', 's')).toBe('string')
  })
  it('converts km/h to mph', () => expect(kmhToMph(160.9344)).toBeCloseTo(100, 10))
})
