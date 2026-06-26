"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

export default function Dashboard() {
  const [projectDir, setProjectDir] = useState("./my-rag");

  const doctor = useQuery({
    queryKey: ["doctor", projectDir],
    queryFn: () => fetch(`/api/doctor?project_dir=${encodeURIComponent(projectDir)}`).then((r) => r.json()),
    refetchInterval: 10000,
  });

  const ps = useQuery({
    queryKey: ["ps", projectDir],
    queryFn: () => fetch(`/api/ps?project_dir=${encodeURIComponent(projectDir)}`).then((r) => r.json()),
    refetchInterval: 5000,
  });

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Dashboard</h1>
      <label className="block">Project dir
        <input className="ml-2 border rounded p-1 font-mono w-96"
          value={projectDir} onChange={(e) => setProjectDir(e.target.value)} />
      </label>

      <section className="rounded border bg-white p-4">
        <h2 className="font-semibold mb-2">Doctor</h2>
        {doctor.isLoading && <p>Checking...</p>}
        {doctor.data?.checks.map((c: { name: string; status: string; detail: string }) => (
          <div key={c.name} className="flex gap-2 text-sm border-b last:border-b-0 py-1">
            <span className={`font-mono uppercase w-12 ${c.status === "fail" ? "text-red-600" : c.status === "warn" ? "text-yellow-600" : "text-green-600"}`}>
              {c.status}
            </span>
            <span className="font-semibold w-24">{c.name}</span>
            <span className="text-neutral-700">{c.detail}</span>
          </div>
        ))}
      </section>

      <section className="rounded border bg-white p-4">
        <h2 className="font-semibold mb-2">Services</h2>
        {ps.isLoading && <p>Loading...</p>}
        {ps.data?.services?.length === 0 && <p className="text-neutral-500">No services running. Run <code>perfectrag up</code>.</p>}
        <table className="w-full text-sm">
          <tbody>
            {ps.data?.services?.map((s: { Name?: string; State?: string; Health?: string }) => (
              <tr key={s.Name} className="border-b">
                <td className="font-mono py-1">{s.Name}</td>
                <td>{s.State}</td>
                <td>{s.Health || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
