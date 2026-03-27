"use client";

import { motion } from "framer-motion";

export default function MetricCard({ label, value, detail, accent = "blue" }) {
  return (
    <motion.div
      className={`metric-card accent-${accent}`}
      initial={{ opacity: 0, y: 18 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
    >
      <p className="metric-label">{label}</p>
      <h3 className="metric-value">{value}</h3>
      {detail ? <p className="metric-detail">{detail}</p> : null}
    </motion.div>
  );
}
