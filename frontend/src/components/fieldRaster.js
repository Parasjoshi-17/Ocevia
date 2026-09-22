/* =========================================================================
   OCEVIA — FIELD RASTER HELPERS

   Shared by SSTLayer and WaveLayer to turn the REAL Open-Meteo points
   returned by GET /api/map-data into a continuous colour field.

   WHAT IS REAL AND WHAT IS DRAWING
   --------------------------------
   Every value here comes from a real Open-Meteo response for a real
   coordinate. The only thing this file adds is INTERPOLATION BETWEEN
   those points so the map looks like a field instead of a dot grid:

     - a raster pixel is filled only if at least one real point lies
       within `searchRadius` of it (about 1.5 grid cells);
     - a pixel further than that from every real point stays fully
       transparent. Nothing is extrapolated into empty ocean, and
       nothing is painted over land, because land has no marine
       points near it.

   This is a visual technique, not new data. The points array stays
   the source of truth, and the tooltip readout always reports a real
   point's own value, never an interpolated one.
   ========================================================================= */

/* Number(null) is 0 and Number("") is 0, so a missing value would silently
   become a real-looking 0 (0 degC SST, 0 m waves). Missing must stay
   missing. */
export const toNum = (v) =>
  v === null || v === undefined || v === "" ? NaN : Number(v);

const DEG = Math.PI / 180;

/* --- Mercator, so the raster lines up with Leaflet's own projection ----- */

const mercY = (lat) =>
  Math.log(Math.tan(Math.PI / 4 + (Math.max(-85, Math.min(85, lat)) * DEG) / 2));

const invMercY = (y) => (2 * Math.atan(Math.exp(y)) - Math.PI / 2) / DEG;

/* --- colour ramps ------------------------------------------------------- */

export function rampColor(anchors, value) {
  if (!Number.isFinite(value)) return null;

  let k = 0;
  while (k < anchors.length - 2 && value > anchors[k + 1].v) k++;

  const a = anchors[k];
  const b = anchors[k + 1];
  const t = b.v === a.v ? 0 : Math.min(1, Math.max(0, (value - a.v) / (b.v - a.v)));

  return a.rgb.map((c, i) => Math.round(c + (b.rgb[i] - c) * t));
}

export const rgbCss = (rgb) => `rgb(${rgb[0]}, ${rgb[1]}, ${rgb[2]})`;

/* Wave height (m). Kept in sync with rules.py's DEFAULT_PROFILE
   thresholds (caution 1.5 m, danger 2.5 m) so the map's colour story
   matches the safety verdict story. */
export const WAVE_ANCHORS = [
  { v: 0.0, rgb: [56, 189, 248] },
  { v: 0.75, rgb: [34, 197, 94] },
  { v: 1.5, rgb: [250, 204, 21] },
  { v: 2.5, rgb: [239, 68, 68] },
  { v: 4.0, rgb: [127, 29, 29] },
];

/* Sea surface temperature (degC), cool -> warm. */
const SST_RAMP = [
  [49, 54, 149],
  [69, 117, 180],
  [116, 173, 209],
  [171, 217, 233],
  [254, 224, 144],
  [253, 174, 97],
  [244, 109, 67],
  [215, 48, 39],
];

/**
 * SST anchors stretched over the range actually present in the data,
 * so the legend always describes the colours on screen. Falls back to
 * a small window when every point is nearly the same temperature.
 */
export function sstAnchorsFor(points) {
  const values = [];

  for (const p of points || []) {
    const v = toNum(p.sea_surface_temperature);
    if (Number.isFinite(v)) values.push(v);
  }

  if (!values.length) return null;

  let min = Math.min(...values);
  let max = Math.max(...values);

  if (max - min < 0.5) {
    const mid = (min + max) / 2;
    min = mid - 0.25;
    max = mid + 0.25;
  }

  const anchors = SST_RAMP.map((rgb, i) => ({
    v: min + ((max - min) * i) / (SST_RAMP.length - 1),
    rgb,
  }));

  return { anchors, min, max };
}

/* --- the raster --------------------------------------------------------- */

/**
 * Inverse-distance interpolation of one field onto a small raster, in
 * Mercator space, returned as a PNG data URL plus its geographic bounds.
 *
 * The raster is deliberately coarse (a few times the data spacing) and
 * is then scaled smoothly by the browser inside a Leaflet ImageOverlay:
 * that keeps zooming and panning free of redraw cost and of the "giant
 * circles when you zoom in" problem, without pretending the model has
 * more resolution than it does.
 */
export function buildFieldRaster(points, valueKey, anchors, options = {}) {
  const {
    oversample = 3, // raster cells per native data cell
    maxCells = 220, // hard cap per axis
    searchFactor = 1.5, // fill radius, in native cells
    power = 3, // IDW exponent
  } = options;

  const data = [];

  for (const p of points || []) {
    const lat = toNum(p.latitude);
    const lon = toNum(p.longitude);
    const value = toNum(p[valueKey]);

    if (Number.isFinite(lat) && Number.isFinite(lon) && Number.isFinite(value)) {
      data.push({ lat, lon, value });
    }
  }

  if (data.length < 3 || typeof document === "undefined") return null;

  let minLat = Infinity;
  let maxLat = -Infinity;
  let minLon = Infinity;
  let maxLon = -Infinity;

  for (const d of data) {
    if (d.lat < minLat) minLat = d.lat;
    if (d.lat > maxLat) maxLat = d.lat;
    if (d.lon < minLon) minLon = d.lon;
    if (d.lon > maxLon) maxLon = d.lon;
  }

  const latSpan = maxLat - minLat;
  const lonSpan = maxLon - minLon;

  if (!(latSpan > 0) || !(lonSpan > 0)) return null;

  const spacing = Math.sqrt((latSpan * lonSpan) / data.length);
  const cell = Math.max(spacing / oversample, 1e-4);

  const nx = Math.min(maxCells, Math.max(2, Math.round(lonSpan / cell) + 1));
  const ny = Math.min(maxCells, Math.max(2, Math.round(latSpan / cell) + 1));

  const radius = spacing * searchFactor;
  const radiusSq = radius * radius;

  const canvas = document.createElement("canvas");
  canvas.width = nx;
  canvas.height = ny;

  const context = canvas.getContext("2d");
  const image = context.createImageData(nx, ny);

  const yTop = mercY(maxLat);
  const yBottom = mercY(minLat);

  let p = 0;

  for (let j = 0; j < ny; j++) {
    /* Rows are uniform in Mercator y, which is how Leaflet stretches an
       ImageOverlay - so the field stays aligned with the coastline at
       every zoom level. */
    const lat = invMercY(yTop - ((yTop - yBottom) * j) / (ny - 1));
    const lonScale = Math.cos(lat * DEG); // a degree of longitude is shorter

    for (let i = 0; i < nx; i++, p += 4) {
      const lon = minLon + (lonSpan * i) / (nx - 1);

      let weightSum = 0;
      let valueSum = 0;
      let exact = null;

      for (const d of data) {
        const dLat = lat - d.lat;
        const dLon = (lon - d.lon) * lonScale;
        const distSq = dLat * dLat + dLon * dLon;

        if (distSq > radiusSq) continue;

        if (distSq < 1e-10) {
          exact = d.value;
          break;
        }

        const weight = 1 / Math.pow(distSq, power / 2);

        weightSum += weight;
        valueSum += d.value * weight;
      }

      if (exact === null && weightSum === 0) {
        /* No real observation within the search radius: leave a hole
           rather than invent a value. This is also what keeps the
           field off the land. */
        image.data[p + 3] = 0;
        continue;
      }

      const value = exact !== null ? exact : valueSum / weightSum;
      const rgb = rampColor(anchors, value);

      if (!rgb) {
        image.data[p + 3] = 0;
        continue;
      }

      image.data[p] = rgb[0];
      image.data[p + 1] = rgb[1];
      image.data[p + 2] = rgb[2];
      image.data[p + 3] = 255;
    }
  }

  context.putImageData(image, 0, 0);

  return {
    url: canvas.toDataURL("image/png"),
    bounds: [
      [minLat, minLon],
      [maxLat, maxLon],
    ],
    cellCount: nx * ny,
    pointCount: data.length,
    spacing,
  };
}

/**
 * Nearest REAL point to a lat/lon, within `maxDistanceDeg`. Used for
 * the hover readout so the number shown is always an observation from
 * the API, never an interpolated pixel.
 */
export function nearestPoint(points, lat, lon, valueKey, maxDistanceDeg) {
  let best = null;
  let bestDistSq = Infinity;

  const lonScale = Math.cos(lat * DEG);

  for (const p of points || []) {
    const pLat = toNum(p.latitude);
    const pLon = toNum(p.longitude);

    if (!Number.isFinite(pLat) || !Number.isFinite(pLon)) continue;
    if (!Number.isFinite(toNum(p[valueKey]))) continue;

    const dLat = lat - pLat;
    const dLon = (lon - pLon) * lonScale;
    const distSq = dLat * dLat + dLon * dLon;

    if (distSq < bestDistSq) {
      bestDistSq = distSq;
      best = p;
    }
  }

  if (!best) return null;

  return Math.sqrt(bestDistSq) <= maxDistanceDeg ? best : null;
}
