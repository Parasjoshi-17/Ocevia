    import { useState } from "react";
    import { useNavigate } from "react-router-dom";

    function Home() {
    const navigate = useNavigate();

    const [city, setCity] = useState("Mumbai");
    const [date, setDate] = useState("Tomorrow");
    const [query, setQuery] = useState("");

    const handleAsk = () => {
        if (!query.trim()) {
        return;
        }

        navigate("/dashboard", {
        state: {
            query,
            city,
            date,
        },
        });
    };

    const handleQuickQuestion = (question) => {
        setQuery(question);

        navigate("/dashboard", {
        state: {
            query: question,
            city,
            date,
        },
        });
    };

    return (
        <div className="home-page">

        {/* HERO */}

        <section className="hero">

            <div className="hero-overlay"></div>

            <div className="hero-content">

            <div className="hero-logo">
                ≈
            </div>

            <h1>OCEVIA</h1>

            <h2>
                Turning Ocean Data into Decisions.
            </h2>

            <p>
                AI-powered marine intelligence for safer
                and smarter fishing decisions.
            </p>

            {/* QUERY BOX */}

            <div className="query-box">

                <div className="query-select-row">

                <select
                    value={city}
                    onChange={(event) =>
                    setCity(event.target.value)
                    }
                >
                    <option>Mumbai</option>
                    <option>Chennai</option>
                    <option>Kochi</option>
                    <option>Visakhapatnam</option>
                    <option>Mangaluru</option>
                    <option>Panaji</option>
                    <option>Puri</option>
                    <option>Veraval</option>
                    <option>Kanyakumari</option>
                    <option>Digha</option>
                </select>

                <select
                    value={date}
                    onChange={(event) =>
                    setDate(event.target.value)
                    }
                >
                    <option>Today</option>
                    <option>Tomorrow</option>
                    <option>Day After Tomorrow</option>
                </select>

                </div>

                <div className="query-input-row">

                <span className="search-icon">
                    ◯
                </span>

                <input
                    type="text"
                    placeholder="Ask about weather, waves, fishing zones or fish species..."
                    value={query}
                    onChange={(event) =>
                    setQuery(event.target.value)
                    }
                    onKeyDown={(event) => {
                    if (event.key === "Enter") {
                        handleAsk();
                    }
                    }}
                />

                <button
                    className="ask-button"
                    onClick={handleAsk}
                >
                    ➤ Ask Ocevia
                </button>

                </div>

                {/* QUICK QUESTIONS */}

                <div className="quick-section">

                <p>Quick Questions</p>

                <div className="quick-buttons">

                    <button
                    onClick={() =>
                        handleQuickQuestion(
                        "Is it safe to go fishing tomorrow?"
                        )
                    }
                    >
                    🛡
                    <span>
                        Is it safe to go fishing
                        tomorrow?
                    </span>
                    </button>

                    <button
                    onClick={() =>
                        handleQuickQuestion(
                        "Where should I go fishing?"
                        )
                    }
                    >
                    🐟
                    <span>
                        Where should I go fishing?
                    </span>
                    </button>

                    <button
                    onClick={() =>
                        handleQuickQuestion(
                        "Which fish are likely here?"
                        )
                    }
                    >
                    🐟
                    <span>
                        Which fish are likely here?
                    </span>
                    </button>

                    <button
                    onClick={() =>
                        handleQuickQuestion(
                        "What will be the weather tomorrow?"
                        )
                    }
                    >
                    ☁
                    <span>
                        What will be the weather
                        tomorrow?
                    </span>
                    </button>

                    <button
                    onClick={() =>
                        handleQuickQuestion(
                        "Show potential fishing zones"
                        )
                    }
                    >
                    📍
                    <span>
                        Show potential fishing
                        zones
                    </span>
                    </button>

                </div>

                </div>

            </div>

            </div>

        </section>


        {/* FEATURE CARDS */}

        <section className="feature-section">

            <FeatureCard
            icon="🛡"
            title="Marine Safety"
            description="Know the sea conditions before you go."
            color="green"
            onClick={() =>
                handleQuickQuestion(
                "Is it safe to go fishing tomorrow?"
                )
            }
            />

            <FeatureCard
            icon="🐟"
            title="Fishing Zones"
            description="Find potential fishing areas with real data."
            color="blue"
            onClick={() =>
                navigate("/map")
            }
            />

            <FeatureCard
            icon="🐠"
            title="Fish Species"
            description="Discover likely species in your region."
            color="purple"
            onClick={() =>
                handleQuickQuestion(
                "Which fish are likely here?"
                )
            }
            />

            <FeatureCard
            icon="☀"
            title="Weather & Ocean"
            description="Explore weather and marine conditions."
            color="orange"
            onClick={() =>
                navigate("/map")
            }
            />

            <FeatureCard
            icon="🗺"
            title="Interactive Map"
            description="Visualize and explore marine zones."
            color="cyan"
            onClick={() =>
                navigate("/map")
            }
            />

        </section>


        {/* LOWER INFORMATION */}

        <section className="home-lower">

            <div className="information-banner">

            <div className="information-content">

                <h2>
                🌊 Smarter Decisions, Safer Seas
                </h2>

                <p>
                Ocevia combines marine data, deterministic
                safety analysis and AI explanations to help
                fishermen and marine stakeholders make
                informed decisions.
                </p>

                <button
                onClick={() => navigate("/map")}
                >
                🗺 Explore Marine Map →
                </button>

            </div>

            <div className="information-points">

                <div>
                <strong>◉</strong>
                <span>Forecast Data</span>
                </div>

                <div>
                <strong>◎</strong>
                <span>AI Assisted</span>
                </div>

                <div>
                <strong>≈</strong>
                <span>Marine Intelligence</span>
                </div>

                <div>
                <strong>✓</strong>
                <span>Safety First</span>
                </div>

            </div>

            </div>


            <div className="recent-queries">

            <div className="section-heading">

                <h2>
                ◷ Recent Queries
                </h2>

                <button
                onClick={() => navigate("/history")}
                >
                View All →
                </button>

            </div>

            <div className="recent-query">
                <span className="query-status caution">
                !
                </span>

                <div>
                <strong>
                    Is it safe to go fishing tomorrow morning?
                </strong>

                <small>
                    Mumbai • Tomorrow
                </small>
                </div>

                <span className="query-badge caution">
                CAUTION
                </span>
            </div>

            <div className="recent-query">
                <span className="query-status safe">
                ✓
                </span>

                <div>
                <strong>
                    Where should I go fishing tomorrow?
                </strong>

                <small>
                    Chennai • Tomorrow
                </small>
                </div>

                <span className="query-badge safe">
                SAFE
                </span>
            </div>

            <div className="recent-query">
                <span className="query-status info">
                i
                </span>

                <div>
                <strong>
                    Which fish are likely near Mumbai?
                </strong>

                <small>
                    Mumbai • Today
                </small>
                </div>

                <span className="query-badge info">
                INFO
                </span>
            </div>

            </div>

        </section>


        {/* FOOTER */}

        <footer className="footer">
            <span>
            OCEVIA
            </span>

            <span>
            Turning Ocean Data into Decisions.
            </span>

            <span>
            Data • AI • Safer Seas
            </span>
        </footer>

        </div>
    );
    }


    function FeatureCard({
    icon,
    title,
    description,
    color,
    onClick,
    }) {
    return (
        <button
        className={`feature-card ${color}`}
        onClick={onClick}
        >

        <div className="feature-icon">
            {icon}
        </div>

        <div className="feature-text">
            <h3>{title}</h3>

            <p>{description}</p>
        </div>

        <span className="feature-arrow">
            →
        </span>

        </button>
    );
    }

    export default Home;