    import { Link, NavLink } from "react-router-dom";

    function Navbar() {
    return (
        <header className="navbar">
        <Link to="/" className="brand">
            <div className="brand-icon">≈</div>

            <div className="brand-text">
            <div className="brand-name">
                OCEVIA
            </div>

            <div className="brand-tagline">
                Turning Ocean Data into Decisions
            </div>
            </div>
        </Link>

        <nav className="nav-links">
            <NavLink
            to="/"
            className={({ isActive }) =>
                isActive ? "nav-link active" : "nav-link"
            }
            >
            Home
            </NavLink>

            <NavLink
            to="/dashboard"
            className={({ isActive }) =>
                isActive ? "nav-link active" : "nav-link"
            }
            >
            Ask
            </NavLink>

            <NavLink
            to="/map"
            className={({ isActive }) =>
                isActive ? "nav-link active" : "nav-link"
            }
            >
            Marine Map
            </NavLink>

            <NavLink
            to="/history"
            className={({ isActive }) =>
                isActive ? "nav-link active" : "nav-link"
            }
            >
            History
            </NavLink>

            <NavLink
            to="/about"
            className={({ isActive }) =>
                isActive ? "nav-link active" : "nav-link"
            }
            >
            About
            </NavLink>

            <button className="theme-button">
            ☼
            </button>

            <button className="profile-button">
            ●
            </button>
        </nav>
        </header>
    );
    }

    export default Navbar;