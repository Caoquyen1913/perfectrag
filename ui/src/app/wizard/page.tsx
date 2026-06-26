"use client";
import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

type Answers = {
  use_case: string;
  modality: string[];
  privacy: string;
  multi_hop: boolean;
  corpus_size: string;
  user_scale: string;
};

const DEFAULT: Answers = {
  use_case: "qa_docs",
  modality: ["text"],
  privacy: "fully_local",
  multi_hop: false,
  corpus_size: "small",
  user_scale: "solo",
};

export default function Wizard() {
  const [step, setStep] = useState(1);
  const [answers, setAnswers] = useState<Answers>(DEFAULT);
  const [projectDir, setProjectDir] = useState("./my-rag");
  const [selectedAddons, setSelectedAddons] = useState<string[]>([]);

  const addons = useQuery({
    queryKey: ["addons"],
    queryFn: () => fetch("/api/addons").then((r) => r.json()),
  });

  const recommend = useMutation({
    mutationFn: (a: Answers) =>
      fetch("/api/recommend", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(a),
      }).then((r) => r.json()),
  });

  const scaffold = useMutation({
    mutationFn: () =>
      fetch("/api/scaffold", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          project_dir: projectDir,
          answers,
          addons: selectedAddons,
          force: true,
        }),
      }).then((r) => r.json()),
  });

  return (
    <div className="space-y-4 max-w-2xl">
      <h1 className="text-2xl font-bold">Wizard</h1>
      <ol className="flex gap-2 text-sm">
        {[1, 2, 3, 4].map((n) => (
          <li key={n} className={`px-3 py-1 rounded ${step === n ? "bg-black text-white" : "bg-neutral-200"}`}>
            Step {n}
          </li>
        ))}
      </ol>

      {step === 1 && (
        <section className="space-y-3 rounded border bg-white p-4">
          <label className="block">Use case
            <select className="ml-2 border rounded p-1"
              value={answers.use_case}
              onChange={(e) => setAnswers({ ...answers, use_case: e.target.value })}>
              <option value="qa_docs">Q&amp;A over docs</option>
              <option value="graphrag">GraphRAG / multi-hop</option>
              <option value="multimodal">Multimodal</option>
              <option value="code_rag">Code search</option>
              <option value="agent_workflow">Agent / workflow</option>
            </select>
          </label>
          <label className="block">Corpus size
            <select className="ml-2 border rounded p-1"
              value={answers.corpus_size}
              onChange={(e) => setAnswers({ ...answers, corpus_size: e.target.value })}>
              <option value="small">Small (&lt;10k)</option>
              <option value="medium">Medium (10k-1M)</option>
              <option value="large">Large (&gt;1M)</option>
            </select>
          </label>
          <label className="block">Multi-hop reasoning
            <input type="checkbox" className="ml-2"
              checked={answers.multi_hop}
              onChange={(e) => setAnswers({ ...answers, multi_hop: e.target.checked })} />
          </label>
          <button className="rounded bg-black text-white px-4 py-2"
            onClick={() => { recommend.mutate(answers); setStep(2); }}>
            Recommend recipe →
          </button>
        </section>
      )}

      {step === 2 && (
        <section className="rounded border bg-white p-4">
          <h2 className="font-semibold">Recommended</h2>
          {recommend.isPending && <p>Thinking...</p>}
          {recommend.data && (
            <pre className="text-xs bg-neutral-100 p-2 overflow-auto">
              {JSON.stringify(recommend.data, null, 2)}
            </pre>
          )}
          <div className="flex gap-2 mt-3">
            <button className="rounded border px-3 py-1" onClick={() => setStep(1)}>Back</button>
            <button className="rounded bg-black text-white px-3 py-1" onClick={() => setStep(3)}>
              Pick addons →
            </button>
          </div>
        </section>
      )}

      {step === 3 && (
        <section className="rounded border bg-white p-4 space-y-2">
          <h2 className="font-semibold">Addons</h2>
          {addons.isLoading && <p>Loading...</p>}
          {addons.data?.map((a: { name: string; description: string }) => (
            <label key={a.name} className="flex items-start gap-2">
              <input
                type="checkbox"
                className="mt-1"
                checked={selectedAddons.includes(a.name)}
                onChange={(e) => {
                  if (e.target.checked) setSelectedAddons([...selectedAddons, a.name]);
                  else setSelectedAddons(selectedAddons.filter((x) => x !== a.name));
                }}
              />
              <div>
                <div className="font-mono text-sm">{a.name}</div>
                <div className="text-xs text-neutral-600">{a.description}</div>
              </div>
            </label>
          ))}
          <div className="flex gap-2 mt-3">
            <button className="rounded border px-3 py-1" onClick={() => setStep(2)}>Back</button>
            <button className="rounded bg-black text-white px-3 py-1" onClick={() => setStep(4)}>
              Next →
            </button>
          </div>
        </section>
      )}

      {step === 4 && (
        <section className="rounded border bg-white p-4 space-y-2">
          <label className="block">Project dir
            <input className="ml-2 border rounded p-1 font-mono w-96"
              value={projectDir}
              onChange={(e) => setProjectDir(e.target.value)} />
          </label>
          <button className="rounded bg-black text-white px-4 py-2"
            disabled={scaffold.isPending}
            onClick={() => scaffold.mutate()}>
            {scaffold.isPending ? "Scaffolding..." : "Scaffold →"}
          </button>
          {scaffold.data && (
            <div className="rounded bg-green-50 border border-green-200 p-3 mt-3">
              <p className="font-semibold">Done!</p>
              <pre className="text-xs">{JSON.stringify(scaffold.data, null, 2)}</pre>
              <p className="mt-2">Next: <code>cd {scaffold.data.project_dir} && perfectrag up</code></p>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
