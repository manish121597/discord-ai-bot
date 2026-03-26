"use client";

export default function ServerList({ servers }) {
  if (!servers.length) {
    return <p className="text-yellow-500">No servers found</p>;
  }

  return (
    <div className="grid md:grid-cols-2 gap-4 mt-4">
      {servers.map((s, i) => (
        <div
          key={i}
          className="bg-neutral-800 p-4 rounded-lg border border-yellow-700"
        >
          <h3 className="text-lg text-yellow-400 font-bold">
            {s.name || "Unknown Server"}
          </h3>

          <p className="text-sm opacity-70">
            ID: {s.id}
          </p>

          <p className="text-sm mt-2">
            Channels: {s.channels?.length || 0}
          </p>
        </div>
      ))}
    </div>
  );
}