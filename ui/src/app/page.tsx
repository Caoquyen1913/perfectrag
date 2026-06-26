"use client";
import { useQuery } from "@tanstack/react-query";

async function fetchHw() {
  const r = await fetch("/api/hw");
  if (!r.ok) throw new Error("hw");
  return r.json();
}

export default function Home() {
  const { data, isLoading, error } = useQuery({ queryKey: ["hw"], queryFn: fetchHw });

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">perfectRAG</h1>
      <p className="text-neutral-600">
        Scaffold a production-ready RAG service in minutes. Pick a template, add addons,
        click deploy.
      </p>

      <section className="rounded border bg-white p-4">
        <h2 className="font-semibold mb-2">Detected hardware</h2>
        {isLoading && <p>Detecting...</p>}
        {error && <p className="text-red-600">Backend not reachable. Start with <code>perfectrag web</code>.</p>}
        {data && (
          <dl className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm">
            <dt className="text-neutral-500">OS / arch</dt><dd>{data.os} ({data.arch})</dd>
            <dt className="text-neutral-500">CPU</dt><dd>{data.cpu_model} — {data.cpu_cores} cores</dd>
            <dt className="text-neutral-500">RAM</dt><dd>{data.ram_gb} GB</dd>
            <dt className="text-neutral-500">GPU</dt><dd>{data.gpu_vendor} / {data.gpu_name || "—"}</dd>
            <dt className="text-neutral-500">VRAM</dt><dd>{data.vram_gb} GB</dd>
            <dt className="text-neutral-500">Tier</dt><dd className="font-bold">{data.tier}</dd>
          </dl>
        )}
      </section>

      <div className="flex gap-3">
        <a href="/wizard" className="rounded bg-black text-white px-4 py-2">Start wizard →</a>
        <a href="/dashboard" className="rounded border px-4 py-2">Open dashboard</a>
      </div>
    </div>
  );
}
