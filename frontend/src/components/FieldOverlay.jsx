import { useEffect, useMemo, useRef } from "react";
import { useMap } from "react-leaflet";
import L from "leaflet";

import { buildFieldRaster, nearestPoint, toNum } from "./fieldRaster";

/* =========================================================================
   OCEVIA — FIELD OVERLAY

   Draws one continuous field (SST or wave height) from the REAL
   Open-Meteo points in /api/map-data.

   The raster is built once per data change (see fieldRaster.js) and put
   on the map as a single L.imageOverlay. Leaflet then reprojects and
   scales that one image itself, so:

     - zooming in keeps a smooth field instead of growing circles,
     - zooming out keeps the whole regional field visible,
     - panning cannot leave anything stale or misaligned,
     - no redraw work and NO new API call happens on map movement.

   Hovering reports the nearest REAL point's value, so the number a
   user reads is always an observation, never an interpolated pixel.
   ========================================================================= */

function FieldOverlay({
  points,
  valueKey,
  anchors,
  paneName,
  zIndex = 405,
  opacity = 0.75,
  formatValue,
  label,
}) {
  const map = useMap();
  const overlayRef = useRef(null);
  const tooltipRef = useRef(null);

  const raster = useMemo(
    () => (anchors ? buildFieldRaster(points, valueKey, anchors) : null),
    [points, valueKey, anchors]
  );

  /* ---------------- the field itself ---------------- */

  useEffect(() => {
    if (!map || !raster) return undefined;

    if (!map.getPane(paneName)) {
      map.createPane(paneName);
      map.getPane(paneName).style.zIndex = zIndex;
    }

    const overlay = L.imageOverlay(raster.url, raster.bounds, {
      pane: paneName,
      opacity,
      interactive: false,
      /* The raster is coarser than the screen on purpose; let the
         browser smooth it rather than showing hard model cells. */
      className: "ocevia-field-overlay",
    });

    overlay.addTo(map);
    overlayRef.current = overlay;

    return () => {
      if (overlayRef.current && map.hasLayer(overlayRef.current)) {
        map.removeLayer(overlayRef.current);
      }
      overlayRef.current = null;
    };
  }, [map, raster, paneName, zIndex, opacity]);

  /* ---------------- hover readout (real points only) ---------------- */

  useEffect(() => {
    if (!map || !raster) return undefined;

    const tooltip = L.tooltip({
      direction: "top",
      offset: [0, -6],
      opacity: 0.95,
      className: "ocevia-field-tooltip",
    });

    tooltipRef.current = tooltip;

    const onMove = (event) => {
      const { lat, lng } = event.latlng;

      const point = nearestPoint(
        points,
        lat,
        lng,
        valueKey,
        raster.spacing * 0.9
      );

      if (!point) {
        if (map.hasLayer(tooltip)) map.closeTooltip(tooltip);
        return;
      }

      tooltip
        .setLatLng([toNum(point.latitude), toNum(point.longitude)])
        .setContent(formatValue(toNum(point[valueKey])))
        .addTo(map);
    };

    const onOut = () => {
      if (map.hasLayer(tooltip)) map.closeTooltip(tooltip);
    };

    map.on("mousemove", onMove);
    map.on("mouseout", onOut);

    return () => {
      map.off("mousemove", onMove);
      map.off("mouseout", onOut);
      if (map.hasLayer(tooltip)) map.closeTooltip(tooltip);
      tooltipRef.current = null;
    };
  }, [map, raster, points, valueKey, formatValue]);

  /* Nothing renders in React: everything lives on the Leaflet map.
     `label` is accepted so callers can document the layer's source
     string in one place; the Dashboard shows it under the map. */
  void label;

  return null;
}

export default FieldOverlay;
