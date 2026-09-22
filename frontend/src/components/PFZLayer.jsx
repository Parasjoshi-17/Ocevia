import { useEffect, useMemo, useRef } from "react";
import { useMap } from "react-leaflet";
import L from "leaflet";

/* =========================================================================
   OCEVIA — PFZ (POTENTIAL FISHING ZONE) LAYER

   Renders ONLY real zones from the official INCOIS PFZ advisory, as
   returned in the normalized `pfz` object (see pfz.py). The SAME object
   arrives in the /api/ask response, so the dashboard does not need a
   second PFZ request.

   pfz shape:
     { available: true, zones: [{latitude, longitude, depth_m?,
       distance_km?, direction?}, ...], sector, advisory_date?, valid_until? }
     or
     { available: false, message: "No current PFZ advisory available ..." }

   This component NEVER draws a marker that isn't in pfz.zones. When
   pfz.available is not true it draws nothing; the parent owns the
   visible "No current PFZ advisory available for this region/date."
   banner (Dashboard.jsx), and can also be told via onUnavailable().
   ========================================================================= */

/* Number(null) is 0 and Number("") is 0, so a missing value would silently
   become a real-looking 0 (0 degC SST, 0 m waves, a wave heading of 0).
   Missing must stay missing. */
const toNum = (v) =>
  v === null || v === undefined || v === "" ? NaN : Number(v);

const PFZ_ICON = L.divIcon({
  className: "ocevia-pfz-marker",
  html: '<div style="font-size:18px;line-height:1;">\u{1F41F}</div>', // 🐟
  iconSize: [22, 22],
  iconAnchor: [11, 11],
});

function tooltipFor(zone) {
  /* Only fields that are really present on the zone are shown. */
  const lines = ["Potential Fishing Zone (INCOIS)"];

  if (Number.isFinite(toNum(zone.depth_m))) {
    lines.push(`Depth: ${zone.depth_m} m`);
  }

  if (Number.isFinite(toNum(zone.distance_km))) {
    lines.push(`Distance: ${zone.distance_km} km`);
  }

  if (zone.direction) {
    lines.push(`Direction: ${zone.direction}`);
  }

  /* Tooltips render HTML, so keep this plain text (no markup). */
  return lines.join(" \u2022 ");
}

function PFZLayer({ pfz, paneName = "ocevia-pfz", onUnavailable }) {
  const map = useMap();
  const layerGroupRef = useRef(null);

  const available = Boolean(
    pfz && typeof pfz === "object" && pfz.available === true
  );

  const message =
    (pfz && typeof pfz === "object" && pfz.message) ||
    "No current PFZ advisory available for this region/date.";

  const validPoints = useMemo(() => {
    if (!available || !Array.isArray(pfz.zones)) {
      return [];
    }

    return pfz.zones.filter((z) => {
      const lat = toNum(z.latitude);
      const lon = toNum(z.longitude);
      return Number.isFinite(lat) && Number.isFinite(lon);
    });
  }, [available, pfz]);

  useEffect(() => {
    if (!available && typeof onUnavailable === "function") {
      onUnavailable(message);
    }
    // Intentionally re-runs only when availability/message actually change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [available, message]);

  useEffect(() => {
    if (!map) return undefined;

    if (!map.getPane(paneName)) {
      map.createPane(paneName);
      map.getPane(paneName).style.zIndex = 620; // above wave/wind/SST panes
    }

    const group = L.layerGroup([], { pane: paneName });

    for (const point of validPoints) {
      const lat = toNum(point.latitude);
      const lon = toNum(point.longitude);

      L.marker([lat, lon], { pane: paneName, icon: PFZ_ICON })
        .bindTooltip(tooltipFor(point), { direction: "top" })
        .addTo(group);
    }

    group.addTo(map);
    layerGroupRef.current = group;

    return () => {
      if (layerGroupRef.current && map.hasLayer(layerGroupRef.current)) {
        map.removeLayer(layerGroupRef.current);
      }
      layerGroupRef.current = null;
    };
  }, [map, validPoints, paneName]);

  return null;
}

export default PFZLayer;
