import React from "react";

type Props = { match?: "sha256" | "phash" | null; dist?: number | null };

const label = (match?: "sha256" | "phash" | null, dist?: number | null) => {
  if (match === "sha256") return "Exact image";
  if (match === "phash") return `Near-duplicate (d=${dist ?? "?"})`;
  return "Unmapped";
};

export default function MatchBadge({ match, dist }: Props) {
  const text = label(match, dist);
  const isExact = match === "sha256";
  const isNear = match === "phash";
  const base =
    "inline-flex items-center px-2 py-0.5 rounded-2xl text-xs font-medium shadow-sm select-none";
  const cls = isExact
    ? base + " bg-green-100 text-green-800"
    : isNear
    ? base + " bg-yellow-100 text-yellow-800"
    : base + " bg-gray-100 text-gray-800";
  return <span className={cls} title={text}>{text}</span>;
}