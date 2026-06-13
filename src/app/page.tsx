'use client';

import { useEffect, useState } from 'react';

type LegalBasis = {
  law: string;
  title: string;
  year: number;
  citation?: string | null;
  effective_date?: string | null;
  status?: string;
  source_url?: string | null;
};

type Benefit = {
  id: string;
  name: string;
  short_name?: string | null;
  category: string;
  description: string;
  benefit_value: string;
  legal_basis: LegalBasis;
  requirements: string[];
  how_to_claim: string[];
  where_to_apply?: string | null;
  lesser_known: boolean;
  notes?: string | null;
};

type MatchResult = {
  benefit: Benefit;
  eligible: boolean;
  score: number;
  matched: string[];
  missing: string[];
};

type QueryResponse = {
  eligible: MatchResult[];
  potential: MatchResult[];
  disclaimer: string;
};

const GENDERS = ['', 'female', 'male'];
const EMPLOYMENT = [
  '',
  'employed',
  'self_employed',
  'unemployed',
  'ofw',
  'student',
  'retired',
  'none',
];

export default function Home() {
  const [flags, setFlags] = useState<Record<string, string>>({});
  const [occupations, setOccupations] = useState<Record<string, string>>({});
  const [optionsError, setOptionsError] = useState<string | null>(null);

  const [age, setAge] = useState('');
  const [gender, setGender] = useState('');
  const [income, setIncome] = useState('');
  const [region, setRegion] = useState('');
  const [employment, setEmployment] = useState('');
  const [occupation, setOccupation] = useState('');
  const [selectedFlags, setSelectedFlags] = useState<Set<string>>(new Set());

  const [result, setResult] = useState<QueryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      fetch('/api/flags').then((r) => r.json()),
      fetch('/api/occupations').then((r) => r.json()),
    ])
      .then(([f, o]) => {
        setFlags(f);
        setOccupations(o);
      })
      .catch(() =>
        setOptionsError(
          'Could not reach the API. Is the FastAPI server running on :8000?'
        )
      );
  }, []);

  function toggleFlag(flag: string) {
    setSelectedFlags((prev) => {
      const next = new Set(prev);
      next.has(flag) ? next.delete(flag) : next.add(flag);
      return next;
    });
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);

    const body: Record<string, unknown> = {};
    if (age) body.age = Number(age);
    if (gender) body.gender = gender;
    if (income) body.monthly_income = Number(income);
    if (region.trim()) body.region = region.trim();
    if (employment) body.employment_status = employment;
    if (occupation) body.occupation = occupation;
    if (selectedFlags.size) body.flags = Array.from(selectedFlags);

    try {
      const res = await fetch('/api/match', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`API returned ${res.status}`);
      setResult(await res.json());
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Something went wrong calling the API.'
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="page">
      <header className="hero">
        <h1>Benepisyoko</h1>
        <p className="tagline">
          Find the Philippine government benefits you may be entitled to —
          including the ones most people never hear about.
        </p>
      </header>

      {optionsError && <div className="banner error">{optionsError}</div>}

      <form className="card form" onSubmit={onSubmit}>
        <div className="grid">
          <label>
            Age
            <input
              type="number"
              min={0}
              max={130}
              value={age}
              onChange={(e) => setAge(e.target.value)}
              placeholder="e.g. 34"
            />
          </label>

          <label>
            Gender
            <select value={gender} onChange={(e) => setGender(e.target.value)}>
              {GENDERS.map((g) => (
                <option key={g} value={g}>
                  {g === '' ? 'Prefer not to say' : g}
                </option>
              ))}
            </select>
          </label>

          <label>
            Monthly income (₱)
            <input
              type="number"
              min={0}
              value={income}
              onChange={(e) => setIncome(e.target.value)}
              placeholder="e.g. 18000"
            />
          </label>

          <label>
            Region / province
            <input
              type="text"
              value={region}
              onChange={(e) => setRegion(e.target.value)}
              placeholder="e.g. NCR"
            />
          </label>

          <label>
            Employment status
            <select
              value={employment}
              onChange={(e) => setEmployment(e.target.value)}
            >
              {EMPLOYMENT.map((s) => (
                <option key={s} value={s}>
                  {s === '' ? '—' : s.replace('_', ' ')}
                </option>
              ))}
            </select>
          </label>

          <label>
            Line of work
            <select
              value={occupation}
              onChange={(e) => setOccupation(e.target.value)}
            >
              <option value="">—</option>
              {Object.entries(occupations).map(([key, desc]) => (
                <option key={key} value={key} title={desc}>
                  {key.replace('_', ' ')}
                </option>
              ))}
            </select>
          </label>
        </div>

        <fieldset className="flags">
          <legend>Do any of these apply to you?</legend>
          <div className="flag-grid">
            {Object.entries(flags).map(([key, desc]) => (
              <label key={key} className="flag" title={desc}>
                <input
                  type="checkbox"
                  checked={selectedFlags.has(key)}
                  onChange={() => toggleFlag(key)}
                />
                <span>{key.replace(/_/g, ' ')}</span>
              </label>
            ))}
          </div>
        </fieldset>

        <button type="submit" disabled={loading}>
          {loading ? 'Searching…' : 'Find my benefits'}
        </button>
      </form>

      {error && <div className="banner error">{error}</div>}

      {result && (
        <section className="results">
          <ResultGroup
            title="You're likely eligible"
            subtitle="Every requirement we could check is met."
            results={result.eligible}
            tone="eligible"
          />
          <ResultGroup
            title="You may also qualify for"
            subtitle="Not ruled out — you'd qualify by meeting or declaring the noted items."
            results={result.potential}
            tone="potential"
          />
          <p className="disclaimer">{result.disclaimer}</p>
        </section>
      )}
    </main>
  );
}

function ResultGroup({
  title,
  subtitle,
  results,
  tone,
}: {
  title: string;
  subtitle: string;
  results: MatchResult[];
  tone: 'eligible' | 'potential';
}) {
  if (!results.length) return null;
  return (
    <div className="group">
      <h2>
        {title} <span className="count">{results.length}</span>
      </h2>
      <p className="subtitle">{subtitle}</p>
      <div className="cards">
        {results.map((r) => (
          <BenefitCard key={r.benefit.id} result={r} tone={tone} />
        ))}
      </div>
    </div>
  );
}

function BenefitCard({
  result,
  tone,
}: {
  result: MatchResult;
  tone: 'eligible' | 'potential';
}) {
  const b = result.benefit;
  const lb = b.legal_basis;
  return (
    <article className={`benefit ${tone}`}>
      <div className="benefit-head">
        <h3>{b.name}</h3>
        <div className="tags">
          <span className="tag category">{b.category.replace('_', ' ')}</span>
          {b.lesser_known && <span className="tag lesser">lesser-known</span>}
        </div>
      </div>

      <p className="value">{b.benefit_value}</p>
      <p className="desc">{b.description}</p>

      {tone === 'potential' && result.missing.length > 0 && (
        <div className="missing">
          <strong>To qualify:</strong>
          <ul>
            {result.missing.map((m, i) => (
              <li key={i}>{m}</li>
            ))}
          </ul>
        </div>
      )}

      <details>
        <summary>Requirements & how to claim</summary>
        {b.requirements.length > 0 && (
          <>
            <h4>Requirements</h4>
            <ul>
              {b.requirements.map((req, i) => (
                <li key={i}>{req}</li>
              ))}
            </ul>
          </>
        )}
        {b.how_to_claim.length > 0 && (
          <>
            <h4>How to claim</h4>
            <ol>
              {b.how_to_claim.map((step, i) => (
                <li key={i}>{step}</li>
              ))}
            </ol>
          </>
        )}
        {b.where_to_apply && (
          <p className="where">
            <strong>Where:</strong> {b.where_to_apply}
          </p>
        )}
      </details>

      <footer className="legal">
        {lb.source_url ? (
          <a href={lb.source_url} target="_blank" rel="noreferrer">
            {lb.law} — {lb.title} ({lb.year})
          </a>
        ) : (
          <span>
            {lb.law} — {lb.title} ({lb.year})
          </span>
        )}
      </footer>
    </article>
  );
}
