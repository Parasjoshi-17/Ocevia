  import {
    BrowserRouter,
    Routes,
    Route,
  } from "react-router-dom";

  import Navbar from "./components/Navbar";

  import Home from "./pages/Home";
  import Dashboard from "./pages/Dashboard";
  import MarineMap from "./pages/MarineMap";
  import History from "./pages/History";
  import About from "./pages/About";

  import "./App.css";

  function App() {
    return (
      <BrowserRouter>

        <Navbar />

        <Routes>

          <Route
            path="/"
            element={<Home />}
          />

          <Route
            path="/dashboard"
            element={<Dashboard />}
          />

          <Route
            path="/map"
            element={<MarineMap />}
          />

          <Route
            path="/history"
            element={<History />}
          />

          <Route
            path="/about"
            element={<About />}
          />

        </Routes>

      </BrowserRouter>
    );
  }

  export default App;