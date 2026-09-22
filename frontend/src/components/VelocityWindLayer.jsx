import { useEffect, useMemo, useRef } from "react";
import { useMap } from "react-leaflet";
import L from "leaflet";

/* =========================================================================
   OCEVIA — VELOCITY WIND LAYER

   Replaces the hand-rolled AnimatedWindField canvas.

   Renders an animated velocity field using leaflet-velocity (WindJS core),
   built ONLY from the real Open-Meteo points returned by
   GET /api/map-data?city=&date=&time=

   Consumed fields (no others are invented):
     latitude, longitude, wind_speed (km/h), wind_direction (deg, FROM),
     wave_height (used purely as the existing marine mask)
   ========================================================================= */

const DEG = Math.PI / 180;

/* Legend buckets in Dashboard.jsx are km/h; the plugin works in m/s.
   45 km/h is the top of the legend => 12.5 m/s. */
const MAX_VELOCITY_MS = 12.5;

/* Anchor colours copied from .wind-low .. .wind-danger in App.css so the
   animation and the on-map legend never disagree. */
const LEGEND_ANCHORS = [
  { ms: 0.0, rgb: [56, 189, 248] }, //  0 km/h
  { ms: 2.78, rgb: [34, 197, 94] }, // 10 km/h
  { ms: 5.56, rgb: [250, 204, 21] }, // 20 km/h
  { ms: 8.33, rgb: [249, 115, 22] }, // 30 km/h
  { ms: 12.5, rgb: [239, 68, 68] }, // 45 km/h
];

/* Pulling every colour toward slate keeps the field readable over OSM
   instead of turning the whole map into a neon raster. */
const MUTE_TARGET = [300, 300, 255];
const MUTE_AMOUNT = 0.01;

/* =========================================================================
   COLOUR SCALE

   leaflet-velocity indexes colorScale linearly across
   [minVelocity, maxVelocity], so the array must be sampled at uniform m/s.
   ========================================================================= */

function buildColorScale(steps = 24, maxVelocity = MAX_VELOCITY_MS) {
  const scale = [];

  for (let s = 0; s < steps; s++) {
    const ms = (s / (steps - 1)) * maxVelocity;

    let k = 0;
    while (k < LEGEND_ANCHORS.length - 2 && ms > LEGEND_ANCHORS[k + 1].ms) {
      k++;
    }

    const a = LEGEND_ANCHORS[k];
    const b = LEGEND_ANCHORS[k + 1];

    const t =
      b.ms === a.ms
        ? 0
        : Math.min(1, Math.max(0, (ms - a.ms) / (b.ms - a.ms)));

    const rgb = a.rgb.map((channel, c) => {
      const blended = channel + (b.rgb[c] - channel) * t;
      return Math.round(blended + (MUTE_TARGET[c] - blended) * MUTE_AMOUNT);
    });

    scale.push(`rgb(${rgb[0]}, ${rgb[1]}, ${rgb[2]})`);
  }

  return scale;
}

/* =========================================================================
   OPEN-METEO POINTS -> WINDJS GRID

   leaflet-velocity cannot consume a scattered point list. It needs two
   regular lat/lon rasters (eastward u, northward v) in row-major order
   starting at the NORTH-WEST corner, because windy.js resolves a sample as:

       i = (lon - lo1) / dx
       j = (la1 - lat) / dy

   The Open-Meteo response is an irregular marine subset, so we resample it
   onto a regular grid with inverse-distance weighting. Cells with no real
   observation inside the search radius stay NaN, which makes WindJS retire
   any particle that drifts there. Nothing is extrapolated over land.
   ========================================================================= */

function buildVelocityData(points, options = {}) {
  const {
    resolutionFactor = 0.34, // output cell size relative to native spacing
    searchFactor = 1.8, // IDW cutoff radius relative to native spacing
    maxCells = 220, // hard cap per axis
  } = options;

  if (!Array.isArray(points) || points.length === 0) {
    return null;
  }

  /* ---------------------------------------------------------------
     1. Filter + convert each real point to a velocity vector.

     wave_height is required, exactly as the previous implementation
     did, so the field stays a marine mask.
     --------------------------------------------------------------- */

  const marine = [];

  for (const point of points) {
    const lat = Number(point.latitude);
    const lon = Number(point.longitude);
    const speedKmh = Number(point.wind_speed);
    const directionFrom = Number(point.wind_direction);
    const waveHeight = Number(point.wave_height);

    if (
      !Number.isFinite(lat) ||
      !Number.isFinite(lon) ||
      !Number.isFinite(speedKmh) ||
      !Number.isFinite(directionFrom) ||
      !Number.isFinite(waveHeight)
    ) {
      continue;
    }

    /* Open-Meteo wind_direction_10m is the direction the wind blows FROM.
       A velocity vector points where the air is GOING, so add 180. */
    const bearingTo = ((directionFrom + 180) % 360) * DEG;

    /* km/h -> m/s, which is what the plugin's velocity scale assumes. */
    const speedMs = speedKmh / 3.6;

    marine.push({
      lat,
      lon,
      u: speedMs * Math.sin(bearingTo), // eastward component
      v: speedMs * Math.cos(bearingTo), // northward component
    });
  }

  if (marine.length < 4) {
    return null;
  }

  /* ---------------------------------------------------------------
     2. Regional bounding box from the real coordinates.
     --------------------------------------------------------------- */

  let minLat = Infinity;
  let maxLat = -Infinity;
  let minLon = Infinity;
  let maxLon = -Infinity;

  for (const m of marine) {
    if (m.lat < minLat) minLat = m.lat;
    if (m.lat > maxLat) maxLat = m.lat;
    if (m.lon < minLon) minLon = m.lon;
    if (m.lon > maxLon) maxLon = m.lon;
  }

  const latSpan = maxLat - minLat;
  const lonSpan = maxLon - minLon;

  if (!(latSpan > 0) || !(lonSpan > 0)) {
    return null;
  }

  /* ---------------------------------------------------------------
     3. Estimate the native grid spacing, then pick an output raster
        finer than it so the field renders smoothly.
     --------------------------------------------------------------- */

  const nativeSpacing = Math.sqrt((latSpan * lonSpan) / marine.length);
  const targetCell = Math.max(nativeSpacing * resolutionFactor, 1e-4);

  const nx = Math.min(maxCells, Math.max(2, Math.round(lonSpan / targetCell) + 1));
  const ny = Math.min(maxCells, Math.max(2, Math.round(latSpan / targetCell) + 1));

  const dx = lonSpan / (nx - 1);
  const dy = latSpan / (ny - 1);

  const searchRadius = nativeSpacing * searchFactor;
  const searchRadiusSq = searchRadius * searchRadius;

  /* ---------------------------------------------------------------
     4. Inverse-distance weighting, north row first.

        u and v are interpolated separately. Averaging the vector
        components rather than the compass bearing avoids the 0/360
        wrap-around artefact.
     --------------------------------------------------------------- */

  const uData = new Array(nx * ny);
  const vData = new Array(nx * ny);

  let p = 0;

  for (let j = 0; j < ny; j++) {
    const lat = maxLat - j * dy;
    const lonScale = Math.cos(lat * DEG); // degrees of longitude are shorter

    for (let i = 0; i < nx; i++, p++) {
      const lon = minLon + i * dx;

      let weightSum = 0;
      let uSum = 0;
      let vSum = 0;
      let exact = null;

      for (const m of marine) {
        const dLat = lat - m.lat;
        const dLon = (lon - m.lon) * lonScale;
        const distSq = dLat * dLat + dLon * dLon;

        if (distSq > searchRadiusSq) {
          continue;
        }

        if (distSq < 1e-10) {
          exact = m;
          break;
        }

        /* 1 / d^3 — sharper than plain 1/d^2, so the resampled field
           stays faithful to each real observation. */
        const weight = 1 / (distSq * Math.sqrt(distSq));

        weightSum += weight;
        uSum += m.u * weight;
        vSum += m.v * weight;
      }

      if (exact) {
        uData[p] = exact.u;
        vData[p] = exact.v;
      } else if (weightSum > 0) {
        uData[p] = uSum / weightSum;
        vData[p] = vSum / weightSum;
      } else {
        /* No real observation nearby: leave a hole rather than invent wind. */
        uData[p] = NaN;
        vData[p] = NaN;
      }
    }
  }

  /* ---------------------------------------------------------------
     5. WindJS record headers.

        parameterCategory 2 / parameterNumber 2 = eastward_wind (u)
        parameterCategory 2 / parameterNumber 3 = northward_wind (v)
     --------------------------------------------------------------- */

  const header = {
    parameterUnit: "m.s-1",
    parameterCategory: 2,
    nx,
    ny,
    lo1: minLon, // west edge
    la1: maxLat, // north edge (row 0)
    dx,
    dy,
    refTime: new Date().toISOString(),
    forecastTime: 0,
  };

  return [
    {
      header: { ...header, parameterNumber: 2, parameterNumberName: "eastward_wind" },
      data: uData,
    },
    {
      header: { ...header, parameterNumber: 3, parameterNumberName: "northward_wind" },
      data: vData,
    },
  ];
}

/* =========================================================================
   COMPONENT
   ========================================================================= */

function VelocityWindLayer({
  points,
  velocityScale = 0.006,
  particleAge = 80,
  particleMultiplier = 0.011,
  lineWidth = 1.8,
  frameRate = 24,
  maxVelocity = MAX_VELOCITY_MS,
  displayValues = false,
  paneName = "oceviawind",
}) {
  const map = useMap();
  const layerRef = useRef(null);

  /* Rebuilt only when the backend hands us a new point array. */
  const velocityData = useMemo(() => buildVelocityData(points), [points]);

  const colorScale = useMemo(
    () => buildColorScale(24, maxVelocity),
    [maxVelocity]
  );

  useEffect(() => {
    if (!map || !velocityData) {
      return undefined;
    }

    let cancelled = false;

    const attach = async () => {
      /* leaflet-velocity's dist bundle reads a global L when it evaluates,
         and ESM imports are hoisted, so a static import would run before
         we could assign it. Dynamic import is the only correct order. */
      if (!window.L) {
        window.L = L;
      }

      await import("leaflet-velocity");

      if (cancelled || !map || !map.getContainer()) {
        return;
      }

      /* Defensive: never stack two velocity layers on the same map. */
      if (layerRef.current) {
        map.removeLayer(layerRef.current);
        layerRef.current = null;
      }

      const layer = L.velocityLayer({
        displayValues,
        displayOptions: {
          velocityType: "Wind",
          position: "bottomleft",
          emptyString: "No wind data",
          angleConvention: "bearingCW",
          speedUnit: "ms",
          directionString: "Direction",
          speedString: "Speed",
        },

        data: velocityData,

        minVelocity: 0,
        maxVelocity,
        velocityScale,
        particleAge,
        particleMultiplier,
        lineWidth,
        frameRate,
        colorScale,

        paneName,
      });

      layer.addTo(map);
      layerRef.current = layer;
    };

    attach();

    return () => {
      cancelled = true;

      const layer = layerRef.current;
      layerRef.current = null;

      if (layer && map && map.hasLayer(layer)) {
        /* onRemove -> _destroyWind: stops the raf loop, clears the canvas,
           drops the mouse control and detaches the canvas layer. */
        map.removeLayer(layer);
      }
    };
  }, [
    map,
    velocityData,
    colorScale,
    velocityScale,
    particleAge,
    particleMultiplier,
    lineWidth,
    frameRate,
    maxVelocity,
    displayValues,
    paneName,
  ]);

  return null;
}

export default VelocityWindLayer;
