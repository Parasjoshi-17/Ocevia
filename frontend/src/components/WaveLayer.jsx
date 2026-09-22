import { useEffect, useMemo, useRef } from "react";
import { useMap } from "react-leaflet";
import L from "leaflet";

import FieldOverlay from "./FieldOverlay";
import { WAVE_ANCHORS, rampColor, rgbCss, toNum } from "./fieldRaster";

/* =========================================================================
   OCEVIA — WAVE LAYER

   Renders wave height + direction from the SAME `points` array already
   returned by GET /api/map-data (Open-Meteo Marine API via the backend).
   Nothing is fetched here and nothing is invented.

     wave_height    -> continuous colour field (FieldOverlay / IDW raster)
     wave_direction -> one arrow per REAL data point

   The arrows are drawn through Leaflet's canvas renderer rather than as
   DOM elements, so a few hundred of them stay cheap and Leaflet keeps
   them correctly projected while zooming and panning. They are thinned
   out at low zoom so the field does not turn into a hairball.
   ========================================================================= */

const DEG = Math.PI / 180;

const formatValue = (metres) => `${metres.toFixed(2)} m`;

function WaveArrows({ points, paneName, zoomThinning }) {
  const map = useMap();
  const layerRef = useRef(null);

  const validPoints = useMemo(() => {
    if (!Array.isArray(points)) return [];

    return points.filter((p) => {
      const lat = toNum(p.latitude);
      const lon = toNum(p.longitude);
      const height = toNum(p.wave_height);
      const direction = toNum(p.wave_direction);

      return (
        Number.isFinite(lat) &&
        Number.isFinite(lon) &&
        Number.isFinite(height) &&
        Number.isFinite(direction)
      );
    });
  }, [points]);

  useEffect(() => {
    if (!map || validPoints.length === 0) return undefined;

    if (!map.getPane(paneName)) {
      map.createPane(paneName);
      map.getPane(paneName).style.zIndex = 412;
    }

    /* Native spacing, so the arrows scale with the data rather than
       with an arbitrary constant. */
    let minLat = Infinity;
    let maxLat = -Infinity;
    let minLon = Infinity;
    let maxLon = -Infinity;

    for (const p of validPoints) {
      const lat = toNum(p.latitude);
      const lon = toNum(p.longitude);
      if (lat < minLat) minLat = lat;
      if (lat > maxLat) maxLat = lat;
      if (lon < minLon) minLon = lon;
      if (lon > maxLon) maxLon = lon;
    }

    const spacing = Math.sqrt(
      Math.max((maxLat - minLat) * (maxLon - minLon), 1e-6) / validPoints.length
    );

    const renderer = L.canvas({ pane: paneName, padding: 0.3 });
    const group = L.layerGroup([], { pane: paneName });

    const draw = () => {
      group.clearLayers();

      /* Thin the arrows out when zoomed away, keep them all when close. */
      const zoom = map.getZoom();
      const stride = zoom >= 7 ? 1 : zoom >= 6 ? 2 : 3;

      let index = 0;

      for (const point of validPoints) {
        if (stride > 1) {
          const lat = toNum(point.latitude);
          const lon = toNum(point.longitude);
          const row = Math.round((lat - minLat) / spacing);
          const column = Math.round((lon - minLon) / spacing);

          if (row % stride !== 0 || column % stride !== 0) {
            index++;
            continue;
          }
        }

        index++;

        const lat = toNum(point.latitude);
        const lon = toNum(point.longitude);
        const height = toNum(point.wave_height);
        const directionFrom = toNum(point.wave_direction);

        const rgb = rampColor(WAVE_ANCHORS, height);
        const color = rgb ? rgbCss(rgb) : "rgb(148,163,184)";

        /* Open-Meteo wave_direction is the direction the waves come
           FROM, so the arrow is drawn pointing where they are
           travelling TO (+180deg) - the same FROM -> TO convention
           VelocityWindLayer uses for wind. */
        const bearingTo = ((directionFrom + 180) % 360) * DEG;

        const length = spacing * 0.85;
        const lonScale = Math.cos(lat * DEG) || 1;

        const tipLat = lat + Math.cos(bearingTo) * length;
        const tipLon = lon + (Math.sin(bearingTo) * length) / lonScale;

        /* Shaft plus two short barbs = a readable arrowhead that still
           rotates correctly with the bearing. */
        const barb = length * 0.35;

        const leftLat = tipLat - Math.cos(bearingTo - 0.45) * barb;
        const leftLon = tipLon - (Math.sin(bearingTo - 0.45) * barb) / lonScale;

        const rightLat = tipLat - Math.cos(bearingTo + 0.45) * barb;
        const rightLon = tipLon - (Math.sin(bearingTo + 0.45) * barb) / lonScale;

        L.polyline(
          [
            [lat, lon],
            [tipLat, tipLon],
            [leftLat, leftLon],
            [tipLat, tipLon],
            [rightLat, rightLon],
          ],
          {
            renderer,
            pane: paneName,
            color: "rgba(15, 23, 42, 0.55)",
            weight: 2.6,
            opacity: 0.55,
            interactive: false,
          }
        ).addTo(group);

        L.polyline(
          [
            [lat, lon],
            [tipLat, tipLon],
            [leftLat, leftLon],
            [tipLat, tipLon],
            [rightLat, rightLon],
          ],
          {
            renderer,
            pane: paneName,
            color,
            weight: 1.4,
            opacity: 0.95,
            interactive: false,
          }
        ).addTo(group);
      }

      void index;
    };

    draw();
    group.addTo(map);
    layerRef.current = group;

    map.on("zoomend", draw);

    return () => {
      map.off("zoomend", draw);

      if (layerRef.current && map.hasLayer(layerRef.current)) {
        map.removeLayer(layerRef.current);
      }

      layerRef.current = null;
    };
  }, [map, validPoints, paneName, zoomThinning]);

  return null;
}

function WaveLayer({ points, paneName = "oceviawaves" }) {
  return (
    <>
      <FieldOverlay
        points={points}
        valueKey="wave_height"
        anchors={WAVE_ANCHORS}
        paneName={paneName}
        zIndex={408}
        opacity={0.62}
        formatValue={formatValue}
        label="Wave height \u2022 Open-Meteo Marine"
      />

      <WaveArrows points={points} paneName={`${paneName}-arrows`} />
    </>
  );
}

export default WaveLayer;
