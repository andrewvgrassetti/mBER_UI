import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { submitJob } from "../lib/api";

export default function JobSubmitPage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    setError(null);

    const form = e.currentTarget;
    const formData = new FormData(form);

    // If a PDB code is provided and no file was selected, remove the empty pdb_file field
    const pdbCode = formData.get("pdb_code");
    const pdbFile = formData.get("pdb_file") as File | null;
    if (pdbCode && (!pdbFile || !pdbFile.name || pdbFile.size === 0)) {
      formData.delete("pdb_file");
    }

    try {
      const result = await submitJob(formData);
      navigate(`/dashboard`);
      console.log("Job submitted:", result.job_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Submission failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Submit New Design Job</h1>

      {error && (
        <div className="bg-destructive/10 border border-destructive/20 text-destructive rounded-md p-3 mb-4">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Target PDB */}
        <div className="space-y-4 rounded-lg border p-4">
          <h2 className="font-semibold">Target Protein</h2>

          <div>
            <label className="block text-sm font-medium mb-1">
              PDB File Upload
            </label>
            <input
              type="file"
              name="pdb_file"
              accept=".pdb,.cif"
              className="block w-full text-sm file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-primary file:text-primary-foreground hover:file:bg-primary/90"
            />
            <p className="text-xs text-muted-foreground mt-1">
              Or enter a PDB code below
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">
              PDB Code (alternative)
            </label>
            <input
              type="text"
              name="pdb_code"
              placeholder="e.g. 1ABC"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">
              Target Name (optional)
            </label>
            <input
              type="text"
              name="target_name"
              placeholder="Defaults to PDB filename"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">
              Target Chains *
            </label>
            <input
              type="text"
              name="target_chains"
              required
              placeholder="e.g. A or A,B"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">
              Hotspot Residues (optional)
            </label>
            <input
              type="text"
              name="hotspot_residues"
              placeholder="e.g. A56 or A56,B20"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            />
          </div>
        </div>

        {/* Design Parameters */}
        <div className="space-y-4 rounded-lg border p-4">
          <h2 className="font-semibold">Design Parameters</h2>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-1">
                Accepted Designs
              </label>
              <input
                type="number"
                name="num_accepted"
                defaultValue={100}
                min={1}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">
                Max Trajectories
              </label>
              <input
                type="number"
                name="max_trajectories"
                defaultValue={10000}
                min={1}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">
                Min iPTM
              </label>
              <input
                type="number"
                name="min_iptm"
                defaultValue={0.75}
                step={0.01}
                min={0}
                max={1}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">
                Min pLDDT
              </label>
              <input
                type="number"
                name="min_plddt"
                defaultValue={0.7}
                step={0.01}
                min={0}
                max={1}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">
              Custom Masked VHH Sequence (optional)
            </label>
            <textarea
              name="masked_vhh_sequence"
              rows={3}
              placeholder="Framework with '*' for design positions"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono"
            />
          </div>
        </div>

        {/* Output Options */}
        <div className="space-y-4 rounded-lg border p-4">
          <h2 className="font-semibold">Output Options</h2>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-1">
                GPU Device
              </label>
              <input
                type="number"
                name="gpu_device"
                defaultValue={0}
                min={0}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              />
            </div>
          </div>

          <div className="flex flex-wrap gap-4">
            <label className="flex items-center space-x-2 text-sm">
              <input type="checkbox" name="skip_animations" value="true" />
              <span>Skip Animations</span>
            </label>
            <label className="flex items-center space-x-2 text-sm">
              <input
                type="checkbox"
                name="skip_pickle"
                value="true"
                defaultChecked
              />
              <span>Skip Pickle</span>
            </label>
            <label className="flex items-center space-x-2 text-sm">
              <input type="checkbox" name="skip_png" value="true" />
              <span>Skip PNG</span>
            </label>
          </div>
        </div>

        {/* Submit */}
        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-md bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          {loading ? "Submitting..." : "Submit Design Job"}
        </button>
      </form>
    </div>
  );
}
