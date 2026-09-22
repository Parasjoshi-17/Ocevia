import FieldOverlay from "./FieldOverlay";
import { sstAnchorsFor } from "./fieldRaster";
import { useMemo } from "react";

/* =========================================================================
   OCEVIA — SST (SEA SURFACE TEMPERATURE) LAYER

   Renders sea_surface_temperature from the SAME `points` array already
   returned by GET /api/map-data (map_data.py's _merge_points includes
   it, sourced from the Open-Meteo Marine API). No new fetch.

   The colours are a continuous field interpolated between those real
   points (see fieldRaster.js). A point whose SST is null contributes
   nothing - it is never guessed - and ocean further than ~1.5 grid
   cells from any real point is left transparent rather than filled in.

   Source label: "Sea Surface Temperature - Open-Meteo Marine".
   ========================================================================= */

const formatValue = (celsius) => `${celsius.toFixed(1)} \u00b0C`;

function SSTLayer({ points, paneName = "oceviasst" }) {
  /* Scale stretched to the SST range actually present, so the legend
     in Dashboard.jsx (built from the same helper) describes exactly
     the colours on screen. */
  const scale = useMemo(() => sstAnchorsFor(points), [points]);

  if (!scale) return null;

  return (
    <FieldOverlay
      points={points}
      valueKey="sea_surface_temperature"
      anchors={scale.anchors}
      paneName={paneName}
      zIndex={405}
      opacity={0.72}
      formatValue={formatValue}
      label="Sea Surface Temperature \u2022 Open-Meteo Marine"
    />
  );
}

export default SSTLayer;
