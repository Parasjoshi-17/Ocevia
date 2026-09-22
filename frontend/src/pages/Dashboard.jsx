    import { useEffect, useState } from "react";
    import { useLocation } from "react-router-dom";

    import {
    MapContainer,
    TileLayer,
    Marker,
    Popup,
    useMap,
    } from "react-leaflet";

    import L from "leaflet";

    import "leaflet/dist/leaflet.css";

    import VelocityWindLayer from "../components/VelocityWindLayer";
    import WaveLayer from "../components/WaveLayer";
    import SSTLayer from "../components/SSTLayer";
    import PFZLayer from "../components/PFZLayer";
    import { sstAnchorsFor, rampColor, rgbCss } from "../components/fieldRaster";


    /* =========================================
    MAP LAYERS
    ========================================= */

    const MAP_LAYERS = [
    { id: "wind", label: "Wind" },
    { id: "waves", label: "Waves" },
    { id: "pfz", label: "Fishing Zones" },
    { id: "sst", label: "SST" },
    ];

    const PFZ_UNAVAILABLE_TEXT =
    "No current PFZ advisory available for this region/date.";

    /* Legend colours are the same anchors WaveLayer.jsx / SSTLayer.jsx use. */
    const WAVE_LEGEND = [
    { color: "rgb(56, 189, 248)", text: "0-0.75 m" },
    { color: "rgb(34, 197, 94)", text: "0.75-1.5 m" },
    { color: "rgb(250, 204, 21)", text: "1.5-2.5 m (caution from 1.5)" },
    { color: "rgb(239, 68, 68)", text: "2.5-4 m (danger from 2.5)" },
    { color: "rgb(127, 29, 29)", text: "4+ m" },
    ];

    /* The SST scale is stretched to the range actually present in the
       returned points, so the legend always describes the colours on
       screen. Built from the same helper the layer itself uses. */

    function sstLegendFor(points) {
    const scale = sstAnchorsFor(points);

    if (!scale) return [];

    return scale.anchors
        .filter((_, index) => index % 2 === 0 || index === scale.anchors.length - 1)
        .map((anchor) => ({
        color: rgbCss(rampColor(scale.anchors, anchor.v)),
        text: `${anchor.v.toFixed(1)} \u00b0C`,
        }));
    }


    /* =========================================
    LEAFLET MARKER ICON
    ========================================= */

    const markerIcon = new L.Icon({
    iconUrl:
        "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png",

    iconRetinaUrl:
        "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png",

    shadowUrl:
        "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png",

    iconSize: [25, 41],

    iconAnchor: [12, 41],

    popupAnchor: [1, -34],

    shadowSize: [41, 41],
    });


    /* =========================================
    MAP VIEW CONTROLLER
    ========================================= */

    /* Fits the viewport to the regional ocean domain that actually came
       back from /api/map-data, so the data never sits as a small patch
       inside an empty map - and never zooms in so far that only the city
       is visible. Runs only when the city or the domain changes, so the
       user's own zooming and panning are left alone (and never trigger a
       fetch). */

    function MapController({ latitude, longitude, bounds }) {
    const map = useMap();

    const boundsKey = bounds
        ? [
            bounds.min_lat,
            bounds.min_lon,
            bounds.max_lat,
            bounds.max_lon,
        ].join(",")
        : "";

    useEffect(() => {
        const hasCentre =
        typeof latitude === "number" &&
        typeof longitude === "number" &&
        !Number.isNaN(latitude) &&
        !Number.isNaN(longitude);

        if (boundsKey) {
        const [minLat, minLon, maxLat, maxLon] =
            boundsKey.split(",").map(Number);

        if ([minLat, minLon, maxLat, maxLon].every(Number.isFinite)) {
            map.flyToBounds(
            [
                [minLat, minLon],
                [maxLat, maxLon],
            ],
            {
                padding: [28, 28],
                maxZoom: 8,
                duration: 1.0,
            }
            );

            return;
        }
        }

        if (hasCentre) {
        map.flyTo([latitude, longitude], 7, { duration: 1.2 });
        }
    }, [latitude, longitude, boundsKey, map]);

    return null;
    }


    /* =========================================
    DASHBOARD
    ========================================= */

    function Dashboard() {
    const location = useLocation();

    const initialQuery =
        location.state?.query ||
        "Can I go fishing tomorrow morning near Mumbai?";


    /* City / day / time window chosen on the Home page. They are sent
       with every /api/ask so the backend never has to guess the city
       from the sentence. Anything the user types inside the query
       ("near Kochi", "tomorrow morning") still takes priority there. */
    const [context, setContext] =
        useState({
        city: location.state?.city,
        target_day: location.state?.date,
        time_window: location.state?.timeWindow,
        });

    const [activeLayer, setActiveLayer] =
        useState("wind");

    const [query, setQuery] =
        useState(initialQuery);

    const [result, setResult] =
        useState(null);

    const [loading, setLoading] =
        useState(true);

    const [error, setError] =
        useState("");

    const [mapData, setMapData] =
        useState(null);

    const [mapLoading, setMapLoading] =
        useState(false);
    
    const [darkMode, setDarkMode] =
    useState(false);
    
    useEffect(() => {
    document.documentElement.setAttribute(
        "data-theme",
        darkMode ? "dark" : "light"
    );
}, [darkMode]);

    /* =========================================
        ASK OCEVIA
        ========================================= */

    const askOcevia = async (
        customQuery = query
    ) => {

        if (!customQuery.trim()) {
        return;
        }


        setLoading(true);

        setError("");

        setMapData(null);


        try {

        const response =
            await fetch(
            "/api/ask",
            {
                method: "POST",

                headers: {
                "Content-Type":
                    "application/json",
                },

                body: JSON.stringify({
                query:
                    customQuery,
                ...(context.city
                    ? { city: context.city }
                    : {}),
                ...(context.target_day
                    ? { target_day: context.target_day }
                    : {}),
                ...(context.time_window
                    ? { time_window: context.time_window }
                    : {}),
                }),
            }
            );


        const data =
            await response.json();


        if (
            !response.ok ||
            data.status !==
            "success"
        ) {

            throw new Error(
            data.error ||
                data.message ||
                "Unable to get a response from Ocevia."
            );
        }


        setResult(data);

        /* Follow-up questions keep the city/day/window the backend
           actually resolved (e.g. after the user typed "near Vizag"). */
        setContext({
            city: data.city,
            target_day: data.target_day,
            time_window: data.time_window,
        });

        } catch (err) {

        console.error(err);

        setError(
            err.message ||
            "Something went wrong while contacting Ocevia."
        );

        } finally {

        setLoading(false);
        }
    };


    /* =========================================
        INITIAL QUERY
        ========================================= */

    useEffect(() => {

        askOcevia(
        initialQuery
        );

        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);


    /* =========================================
        FETCH SPATIAL MAP DATA
        ========================================= */

    useEffect(() => {

        if (!result) {
        return;
        }


        const city =
        result.city;

        const forecastDate =
        result.forecast_date;


        if (
        !city ||
        !forecastDate
        ) {
        return;
        }


        /* Same hour the safety verdict was decided on (the worst hour
           of the requested window), so map and verdict agree. */
        let forecastTime =
        "12:00";


        if (
        result.worst_period
        ) {

        const parts =
            result.worst_period
            .split("T");


        if (
            parts.length === 2
        ) {

            forecastTime =
            parts[1].slice(
                0,
                5
            );
        }
        }


        let cancelled = false;


        const fetchMapData =
        async () => {

            try {

            setMapLoading(
                true
            );


            const params =
                new URLSearchParams({
                city,
                date:
                    forecastDate,
                time:
                    forecastTime,
                });


            const response =
                await fetch(
                `/api/map-data?${params.toString()}`
                );


            const data =
                await response.json();


            if (
                !response.ok ||
                data.status !==
                "success"
            ) {

                throw new Error(
                data.error ||
                    data.message ||
                    "Unable to load spatial map data."
                );
            }


            if (!cancelled) {
                setMapData(
                data
                );
            }

            } catch (err) {

            console.error(
                "Map data error:",
                err
            );

            if (!cancelled) {
                setMapData(
                null
                );
            }

            } finally {

            if (!cancelled) {
                setMapLoading(
                false
                );
            }
            }
        };


        fetchMapData();

        return () => {
        cancelled = true;
        };

        /* Depends on the whole result object: askOcevia() clears
           mapData on every question, so the map must be re-fetched on
           every new result even when city/date/hour are unchanged. */
    }, [result]);


    /* =========================================
        LOADING
        ========================================= */

    if (loading) {

        return (
        <main className="dashboard-page dashboard-loading">

            <div className="loading-card">

            <div className="loading-spinner"></div>

            <h2>
                Ocevia is analyzing the sea...
            </h2>

            <p>
                Fetching weather and marine forecast data.
            </p>

            <div className="loading-steps">

                <span>
                ✓ Understanding query
                </span>

                <span>
                ◌ Fetching weather
                </span>

                <span>
                ◌ Fetching marine conditions
                </span>

                <span>
                ◌ Running safety analysis
                </span>

            </div>

            </div>

        </main>
        );
    }


    /* =========================================
        ERROR
        ========================================= */

    if (error) {

        return (
        <main className="dashboard-page dashboard-loading">

            <div className="error-card">

            <h2>
                Unable to load Ocevia
            </h2>

            <p>
                {error}
            </p>

            <button
                onClick={() =>
                askOcevia()
                }
                className="primary-button"
            >
                Try Again
            </button>

            </div>

        </main>
        );
    }


    if (!result) {
        return null;
    }


    /* =========================================
        RESULT DATA
        ========================================= */

    const coordinates =
        result.coordinates ||
        {};


    const latitude =
        Number(
        coordinates.latitude
        );


    const longitude =
        Number(
        coordinates.longitude
        );


    const verdict =
        result.verdict ||
        "DATA UNAVAILABLE";


    const verdictClass =
        verdict === "SAFE"
        ? "safe"
        : verdict ===
            "CAUTION"
            ? "caution"
            : verdict ===
                "DO NOT VENTURE"
            ? "danger"
            : "unavailable";


    const metrics =
        result.metrics ||
        {};


    const pfz =
        result.pfz ||
        {};

    const pfzAvailable =
        pfz.available === true &&
        Array.isArray(pfz.zones) &&
        pfz.zones.length > 0;

    const fishing =
        result.fishing ||
        {};

    /* SST of the same hour the wave/wind metrics come from
       (the worst hour of the requested window). */
    const worstHour =
        (result.hourly_data || [])
        .find(
            (hour) =>
            hour.time === result.worst_period
        );

    const windowHours =
        Array.isArray(result.selected_hourly_data)
        ? result.selected_hourly_data
        : (result.hourly_data || []);

    const mapPoints =
        Array.isArray(mapData?.points) &&
        mapData.points.length > 0
        ? mapData.points
        : null;

    const mapHour =
        mapData?.time
        ? ` \u2022 ${mapData.time} IST`
        : "";

    /* Honest label: the colours between the model points are drawn by
       interpolation, they are not extra observations. */
    const fieldNote =
        mapPoints
        ? ` \u2022 ${mapPoints.length} model points, interpolated for display`
        : "";

    let mapNote;

    if (activeLayer === "pfz") {
        mapNote = pfzAvailable
        ? `${pfz.zones.length} INCOIS potential fishing zone points${pfz.sector ? " \u2022 " + pfz.sector : ""}`
        : PFZ_UNAVAILABLE_TEXT;
    } else if (mapLoading) {
        mapNote = "Loading forecast grid...";
    } else if (!mapPoints) {
        mapNote = "Spatial forecast data unavailable.";
    } else if (activeLayer === "waves") {
        mapNote = `Wave height (colour) and direction (arrows) \u2022 Open-Meteo Marine${mapHour}${fieldNote}`;
    } else if (activeLayer === "sst") {
        mapNote = `Sea Surface Temperature \u2022 Open-Meteo Marine${mapHour}${fieldNote}`;
    } else {
        mapNote = `Animated wind field \u2022 Open-Meteo Forecast${mapHour}${fieldNote}`;
    }


    /* =========================================
        RENDER
        ========================================= */

    return (
        <main className="dashboard-page">


        {/* =====================================
            QUERY BAR
        ===================================== */}

<section className="dashboard-query">

    <div className="query-header-row">

        <div className="query-title">
            Ask Ocevia
        </div>

        <button
            className="dashboard-theme-button"
            onClick={() => setDarkMode(!darkMode)}
            aria-label="Toggle dark mode"
            title={
                darkMode
                    ? "Switch to light mode"
                    : "Switch to dark mode"
            }
        >
            {darkMode ? "☀️" : "🌙"}
        </button>

    </div>


            <div className="dashboard-query-box">

            <span>
                ⌕
            </span>


            <input
                value={query}
                onChange={(event) =>
                setQuery(
                    event.target.value
                )
                }
                onKeyDown={(event) => {

                if (
                    event.key ===
                    "Enter"
                ) {

                    askOcevia();
                }

                }}
                placeholder="Ask about the ocean..."
            />


            <button
                onClick={() =>
                askOcevia()
                }
                className="primary-button"
            >
                ➤ Ask
            </button>

            </div>

        </section>


        {/* =====================================
            MAIN CONTENT
        ===================================== */}

        <section className="dashboard-grid">


            {/* ===================================
                MAP
            =================================== */}

            <div className="map-card">

            <div className="map-header">

                <div>

                <h2>
                    🗺 Marine Map
                </h2>

                <p>
                    {result.city}
                    {" • "}
                    {result.target_day}
                </p>

                </div>


                <div className="map-live-badge">

                Forecast Data

                </div>

            </div>


            <div className="map-wrapper">

                <MapContainer
                center={[
                    latitude,
                    longitude,
                ]}
                zoom={7}
                minZoom={4}
                maxZoom={11}
                scrollWheelZoom={true}
                className="ocevia-map"
                >

                <TileLayer
                    attribution='&copy; OpenStreetMap contributors'
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                />


                <MapController
                    latitude={
                    latitude
                    }
                    longitude={
                    longitude
                    }
                    bounds={
                    mapData?.data_bounds ||
                    mapData?.region
                    }
                />


                {/* =================================
                    ANIMATED WIND FIELD
                ================================= */}

                {activeLayer === "wind" && mapPoints && (
                    <VelocityWindLayer
                    points={
                        mapPoints
                    }
                    />
                )}


                {/* =================================
                    WAVE HEIGHT + DIRECTION
                ================================= */}

                {activeLayer === "waves" && mapPoints && (
                    <WaveLayer
                    points={
                        mapPoints
                    }
                    />
                )}


                {/* =================================
                    SEA SURFACE TEMPERATURE
                ================================= */}

                {activeLayer === "sst" && mapPoints && (
                    <SSTLayer
                    points={
                        mapPoints
                    }
                    />
                )}


                {/* =================================
                    INCOIS POTENTIAL FISHING ZONES
                    (draws nothing unless real zones exist)
                ================================= */}

                {activeLayer === "pfz" && (
                    <PFZLayer
                    pfz={
                        pfz
                    }
                    />
                )}


                {/* =================================
                    SELECTED CITY
                ================================= */}

                <Marker
                    position={[
                    latitude,
                    longitude,
                    ]}
                    icon={
                    markerIcon
                    }
                >

                    <Popup>

                    <strong>
                        {result.city}
                    </strong>

                    <br />

                    {result.state}

                    <br />

                    Safety:{" "}
                    {verdict}

                    </Popup>

                </Marker>

                </MapContainer>


                {/* =================================
                    MAP CONTROLS
                ================================= */}

                <div className="map-controls">

                {MAP_LAYERS.map((layer) => (
                    <button
                    key={layer.id}
                    className={
                        activeLayer === layer.id
                        ? "active"
                        : ""
                    }
                    onClick={() =>
                        setActiveLayer(layer.id)
                    }
                    >
                    {layer.label}
                    </button>
                ))}

                </div>


                {/* =================================
                    MAP NOTE
                ================================= */}

                <div className="map-note">

                {mapNote}

                </div>


                {/* =================================
                    PFZ UNAVAILABLE STATE
                ================================= */}

                {activeLayer === "pfz" && !pfzAvailable && (
                <div
                    role="status"
                    style={{
                    position: "absolute",
                    top: 12,
                    left: "50%",
                    transform: "translateX(-50%)",
                    zIndex: 1000,
                    maxWidth: "80%",
                    padding: "10px 16px",
                    borderRadius: 10,
                    background: "#fff7ed",
                    border: "1px solid #fdba74",
                    color: "#7c2d12",
                    fontSize: 14,
                    fontWeight: 600,
                    textAlign: "center",
                    boxShadow: "0 2px 8px rgba(0,0,0,0.2)",
                    }}
                >
                    {pfz.message || PFZ_UNAVAILABLE_TEXT}
                </div>
                )}


                {/* =================================
                    LEGENDS (one per layer)
                ================================= */}

                {activeLayer === "wind" && (
                <div className="wind-legend">

                <strong>
                    WIND SPEED
                </strong>

                <div>
                    <span className="legend-dot wind-low"></span>
                    0–10 km/h
                </div>

                <div>
                    <span className="legend-dot wind-medium"></span>
                    10–20 km/h
                </div>

                <div>
                    <span className="legend-dot wind-high"></span>
                    20–30 km/h
                </div>

                <div>
                    <span className="legend-dot wind-strong"></span>
                    30–45 km/h
                </div>

                <div>
                    <span className="legend-dot wind-danger"></span>
                    45+ km/h
                </div>

                </div>
                )}

                {activeLayer === "waves" && (
                <div className="wind-legend">

                <strong>
                    WAVE HEIGHT
                </strong>

                {WAVE_LEGEND.map((item) => (
                    <div key={item.text}>
                    <span
                        className="legend-dot"
                        style={{ background: item.color }}
                    ></span>
                    {item.text}
                    </div>
                ))}

                </div>
                )}

                {activeLayer === "sst" && (
                <div className="wind-legend">

                <strong>
                    SEA SURFACE TEMP
                </strong>

                {sstLegendFor(mapPoints).map((item) => (
                    <div key={item.text}>
                    <span
                        className="legend-dot"
                        style={{ background: item.color }}
                    ></span>
                    {item.text}
                    </div>
                ))}

                </div>
                )}

            </div>

            </div>


            {/* ===================================
                DECISION PANEL
            =================================== */}

            <aside className="decision-panel">


            {/* LOCATION */}

            <div className="location-heading">

                <div>

                <h1>
                    {result.city}
                </h1>

                <p>
                    {result.target_day}
                    {" • "}
                    {result.time_window}
                </p>

                </div>


                <div className="forecast-date">
                {result.forecast_date}
                </div>

            </div>


            {/* SAFETY */}

            <section
                className={`safety-card ${verdictClass}`}
            >

                <div className="safety-icon">

                {verdict ===
                "SAFE"
                    ? "✓"
                    : "!"}

                </div>


                <div>

                <span className="card-label">
                    MARINE SAFETY
                </span>


                <h2>
                    {result.badge_text_en ||
                    verdict}
                </h2>


                <p>
                    {result.advisory}
                </p>

                </div>

            </section>


            {/* METRICS */}

            <section className="metrics-grid">

                <Metric
                icon="〰"
                value={
                    metrics.wave_height_m
                }
                unit="m"
                label="Wave Height"
                />


                <Metric
                icon="≋"
                value={
                    metrics.wind_speed_kmh
                }
                unit="km/h"
                label="Wind Speed"
                />


                <Metric
                icon="≋"
                value={
                    metrics.wind_gusts_kmh
                }
                unit="km/h"
                label="Wind Gust"
                />


                <Metric
                icon="°"
                value={
                    worstHour
                    ?.sea_surface_temperature
                }
                unit="°C"
                label="Sea Surface Temp"
                />

            </section>


            {/* FISHING OPPORTUNITY
                Separate from MARINE SAFETY above. Safety always wins:
                fishing.message already says "Do not venture" when the
                verdict is DO NOT VENTURE, even if a PFZ advisory exists. */}

            <section className="suitability-card">

                <div className="suitability-icon">
                🐟
                </div>


                <div>

                <span className="card-label">
                    FISHING OPPORTUNITY
                </span>


                <h2>
                    {fishing.label ||
                    "Fishing opportunity unavailable"}
                </h2>


                <p>
                    {fishing.message ||
                    PFZ_UNAVAILABLE_TEXT}
                </p>


                {pfz.sector && (
                    <p>
                    <small>
                        INCOIS sector: {pfz.sector}
                        {pfz.advisory_date && pfz.valid_until
                        ? ` \u2022 advisory ${pfz.advisory_date} to ${pfz.valid_until}`
                        : ""}
                    </small>
                    </p>
                )}


                {!pfzAvailable && pfz.detail && (
                    <p>
                    <small>
                        {pfz.detail}
                        {pfz.source_url && (
                        <>
                            {" "}
                            <a
                            href={pfz.source_url}
                            target="_blank"
                            rel="noreferrer"
                            >
                            View the official INCOIS advisory
                            </a>
                        </>
                        )}
                    </small>
                    </p>
                )}


                {fishing.environment
                    ?.sea_surface_temperature_c && (
                    <p>
                    <small>
                        Sea surface temperature in this window:{" "}
                        {formatValue(
                        fishing.environment
                            .sea_surface_temperature_c.min
                        )}
                        {" \u2013 "}
                        {formatValue(
                        fishing.environment
                            .sea_surface_temperature_c.max
                        )}
                        {" \u00b0C (context only, not scored)"}
                    </small>
                    </p>
                )}

                </div>

            </section>


            {/* AI EXPLANATION */}

            <section className="explanation-card">

                <div className="explanation-heading">

                <span>
                    ✨
                </span>


                <h2>
                    Ocevia explains
                </h2>

                </div>


                <p>
                {result.explanation}
                </p>

            </section>


            {/* KEY INFORMATION */}

            <section className="key-info">

                <h2>
                Key Information
                </h2>


                <div className="key-info-grid">

                <div>

                    <span>
                    Location
                    </span>

                    <strong>
                    {result.city}
                    </strong>

                </div>


                <div>

                    <span>
                    State
                    </span>

                    <strong>
                    {result.state}
                    </strong>

                </div>


                <div>

                    <span>
                    Forecast
                    </span>

                    <strong>
                    {result.forecast_date}
                    </strong>

                </div>


                <div>

                    <span>
                    Hours
                    </span>

                    <strong>
                    {result.hours_evaluated}
                    </strong>

                </div>

                </div>

            </section>

            </aside>

        </section>


        {/* =====================================
            HOURLY FORECAST
        ===================================== */}

        <section className="forecast-card">

            <div className="forecast-heading">

            <div>

                <h2>
                Hourly Forecast
                </h2>

                <p>
                {result.time_window}
                </p>

            </div>


            <span>
                {result.hours_evaluated}
                {" "}
                hours
            </span>

            </div>


            <div className="forecast-table-wrapper">

            <table>

                <thead>

                <tr>

                    <th>
                    Time
                    </th>

                    <th>
                    Wave
                    </th>

                    <th>
                    Wind
                    </th>

                    <th>
                    Gust
                    </th>

                    <th>
                    SST
                    </th>

                </tr>

                </thead>


                <tbody>

                {windowHours
                    .filter(
                    (hour) => {

                        if (
                        !hour.time
                        ) {
                        return false;
                        }

                        return hour.time.includes(
                        result.forecast_date
                        );
                    }
                    )
                    .map(
                    (hour) => (

                        <tr
                        key={
                            hour.time
                        }
                        >

                        <td>
                            {
                            hour.time.split(
                                "T"
                            )[1]
                            }
                        </td>


                        <td>
                            {formatValue(
                            hour.wave_height
                            )}
                            {" "}
                            m
                        </td>


                        <td>
                            {formatValue(
                            hour.wind_speed
                            )}
                            {" "}
                            km/h
                        </td>


                        <td>
                            {formatValue(
                            hour.wind_gust
                            )}
                            {" "}
                            km/h
                        </td>


                        <td>
                            {formatValue(
                            hour.sea_surface_temperature
                            )}
                            {" "}
                            °C
                        </td>

                        </tr>

                    )
                    )}

                </tbody>

            </table>

            </div>

        </section>


        {/* =====================================
            DATA SOURCES
        ===================================== */}

        <section className="sources-bar">

            <span>
            Weather:
            <strong>
                Open-Meteo Forecast API
            </strong>
            </span>


            <span>
            Marine:
            <strong>
                Open-Meteo Marine API
            </strong>
            </span>


            <span>
            Fishing zones:
            <strong>
                INCOIS PFZ Advisory
            </strong>
            </span>


            <span>
            Map:
            <strong>
                OpenStreetMap
            </strong>
            </span>

        </section>

        </main>
    );
    }


    /* =========================================
    METRIC COMPONENT
    ========================================= */

    function Metric({
    icon,
    value,
    unit,
    label,
    }) {
    return (
        <div className="metric-card">

        <div className="metric-icon">
            {icon}
        </div>


        <div>

            <strong>

            {formatValue(
                value
            )}

            <small>
                {unit}
            </small>

            </strong>


            <span>
            {label}
            </span>

        </div>

        </div>
    );
    }


    /* =========================================
    FORMAT VALUE
    ========================================= */

    function formatValue(value) {

    if (
        value === null ||
        value === undefined ||
        Number.isNaN(
        Number(value)
        )
    ) {
        return "—";
    }


    return Number(
        value
    ).toFixed(2);
    }


    export default Dashboard;