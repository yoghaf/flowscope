import { createBrowserRouter } from "react-router";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import FlowScanner from "./pages/FlowScanner";
import CoinDetail from "./pages/CoinDetail";
import Alerts from "./pages/Alerts";

export const router = createBrowserRouter([
  {
    path: "/",
    Component: Layout,
    children: [
      { index: true, Component: Dashboard },
      { path: "scanner", Component: FlowScanner },
      { path: "coin/:symbol", Component: CoinDetail },
      { path: "alerts", Component: Alerts },
    ],
  },
]);
