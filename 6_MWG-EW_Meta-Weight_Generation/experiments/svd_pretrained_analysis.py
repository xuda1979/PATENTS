"""SVD energy capture and cosine similarity analysis on pretrained LLM weights.

Runs on ai1 (Ascend 910B2 NPU) or any machine with HuggingFace transformers.
Downloads a small open-source LLM and measures SVD energy / cosine similarity
for FFN projections at various ranks.

Usage:
    python3 experiments/svd_pretrained_analysis.py
"""
from __future__ import annotations
import json, os, time, sys
from dataclasses import dataclass

import torch
import torch.nn as nn

# Try to use transformers; if not available, fall back to manual random-like
try:
    from transformers import AutoModelForCausalLM, AutoConfig
    HAS_TF = True
except ImportError:
    HAS_TF = False

def svd_analysis_single(W: torch.Tensor, ranks: list[int]) -> dict:
    """Analyze SVD energy capture and cosine similarity for a weight matrix."""
    W_f = W.float()
    # Full SVD
    U, S, Vh = torch.linalg.svd(W_f, full_matrices=False)
    total_energy = (S ** 2).sum().item()
    
    results = {}
    for r in ranks:
        if r > min(W_f.shape):
            continue
        # Truncated reconstruction
        U_r = U[:, :r]
        S_r = S[:r]
        Vh_r = Vh[:r, :]
        W_approx = (U_r * S_r.unsqueeze(0)) @ Vh_r
        
        # Energy capture
        energy_r = (S_r ** 2).sum().item()
        energy_pct = energy_r / total_energy * 100
        
        # Cosine similarity (flattened)
        cos_sim = torch.nn.functional.cosine_similarity(
            W_f.reshape(1, -1), W_approx.reshape(1, -1)
        ).item()
        
        # Relative Frobenius error
        rel_err = (W_f - W_approx).norm().item() / W_f.norm().item()
        
        # Max absolute error
        max_abs = (W_f - W_approx).abs().max().item()
        
        results[r] = {
            'rank': r,
            'energy_pct': round(energy_pct, 4),
            'cosine_similarity': round(cos_sim, 6),
            'relative_frobenius_error': round(rel_err, 6),
            'max_abs_error': round(max_abs, 4),
        }
    return results

def analyze_model(model_name: str, ranks: list[int]) -> dict:
    """Load a pretrained model and analyze all FFN projections."""
    print(f"\n{'='*60}")
    print(f"Analyzing: {model_name}")
    print(f"{'='*60}")
    
    if not HAS_TF:
        print("ERROR: transformers not installed. Install with: pip install transformers")
        return {}
    
    t0 = time.time()
    print(f"Loading model (CPU, float16 → float32 for SVD)...")
    
    try:
        model = AutoModelForCausalLM.from_pretrained(
            model_name, 
            torch_dtype=torch.float16,
            device_map='cpu',
            low_cpu_mem_usage=True,
            trust_remote_code=True,
        )
    except Exception as e:
        print(f"Failed to load model: {e}")
        # Try with config only
        try:
            config = AutoConfig.from_pretrained(model_name, trust_remote_code=True)
            print(f"Config loaded: hidden={config.hidden_size}, intermediate={config.intermediate_size}, layers={config.num_hidden_layers}")
        except:
            pass
        return {}
    
    print(f"Model loaded in {time.time()-t0:.1f}s")
    
    # Find FFN projection layers
    all_results = {}
    layer_count = 0
    
    for name, param in model.named_parameters():
        # Match common FFN projection names
        is_ffn = any(k in name for k in ['mlp.gate_proj', 'mlp.up_proj', 'mlp.down_proj',
                                           'feed_forward.w1', 'feed_forward.w2', 'feed_forward.w3',
                                           'fc1', 'fc2', 'gate_proj', 'up_proj', 'down_proj'])
        if not is_ffn:
            continue
        if param.dim() != 2:
            continue
        
        W = param.data
        d, m = W.shape
        print(f"\n  {name}: shape=({d}, {m}), dtype={W.dtype}")
        
        res = svd_analysis_single(W, ranks)
        all_results[name] = {
            'shape': [d, m],
            'dtype': str(W.dtype),
            'total_params_mib': round(d * m * 2 / 1024 / 1024, 2),  # fp16
            'ranks': res,
        }
        
        for r, v in sorted(res.items()):
            print(f"    r={r:4d}: energy={v['energy_pct']:7.3f}%, cos={v['cosine_similarity']:.6f}, "
                  f"rel_err={v['relative_frobenius_error']:.6f}")
        
        layer_count += 1
        # Analyze first 6 layers (2 per FFN block x 3 blocks = up to 6 projections from first 2 layers)
        if layer_count >= 12:
            print(f"\n  (Analyzed {layer_count} projections, stopping early for speed)")
            break
    
    # Summary statistics
    summary = {}
    for r in ranks:
        energies = []
        cosines = []
        for layer_res in all_results.values():
            if r in layer_res['ranks']:
                energies.append(layer_res['ranks'][r]['energy_pct'])
                cosines.append(layer_res['ranks'][r]['cosine_similarity'])
        if energies:
            summary[r] = {
                'mean_energy_pct': round(sum(energies)/len(energies), 3),
                'min_energy_pct': round(min(energies), 3),
                'max_energy_pct': round(max(energies), 3),
                'mean_cosine': round(sum(cosines)/len(cosines), 6),
                'min_cosine': round(min(cosines), 6),
                'max_cosine': round(max(cosines), 6),
                'n_layers': len(energies),
            }
            print(f"\n  Summary r={r}: energy={summary[r]['mean_energy_pct']:.1f}% "
                  f"[{summary[r]['min_energy_pct']:.1f}%-{summary[r]['max_energy_pct']:.1f}%], "
                  f"cos={summary[r]['mean_cosine']:.4f} "
                  f"[{summary[r]['min_cosine']:.4f}-{summary[r]['max_cosine']:.4f}]")
    
    del model
    
    return {
        'model': model_name,
        'ranks': ranks,
        'per_layer': all_results,
        'summary': summary,
        'analysis_time_s': round(time.time() - t0, 1),
    }


def main():
    ranks = [32, 64, 128, 256]
    
    # Try models in order of preference (smaller first for speed)
    models_to_try = [
        'Qwen/Qwen2.5-1.5B',      # Small, widely available
        'Qwen/Qwen2.5-7B',         # Medium
        'meta-llama/Llama-2-7b-hf', # Classic reference (may need auth)
    ]
    
    all_results = {}
    for model_name in models_to_try:
        try:
            result = analyze_model(model_name, ranks)
            if result:
                all_results[model_name] = result
                # If we got a 7B+ model, that's sufficient
                config_size = None
                try:
                    config = AutoConfig.from_pretrained(model_name, trust_remote_code=True)
                    config_size = config.hidden_size
                except:
                    pass
                if config_size and config_size >= 4096:
                    print(f"\n✓ Got 7B-class model ({model_name}), sufficient for patent evidence")
                    break
        except Exception as e:
            print(f"Skipping {model_name}: {e}")
            continue
    
    if not all_results:
        print("\nERROR: Could not load any pretrained model. Check network/auth.")
        sys.exit(1)
    
    # Save results
    out_dir = os.path.join(os.path.dirname(__file__), '..', 'results')
    os.makedirs(out_dir, exist_ok=True)
    ts = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
    out_path = os.path.join(out_dir, f'svd_pretrained_{ts}.json')
    
    with open(out_path, 'w') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to {out_path}")
    
    # Print disclosure-ready table
    print("\n" + "="*70)
    print("DISCLOSURE-READY TABLE (copy to patent)")
    print("="*70)
    for model_name, result in all_results.items():
        print(f"\n### Model: {model_name}")
        print(f"| 秩 r | SVD 能量捕获 | 余弦相似度 (mean) | 余弦相似度 (min) | 相对 Frobenius 误差 |")
        print(f"|------|-------------|------------------|-----------------|-------------------|")
        for r in ranks:
            if r in result['summary']:
                s = result['summary'][r]
                print(f"| {r} | {s['mean_energy_pct']:.1f}% | {s['mean_cosine']:.4f} | {s['min_cosine']:.4f} | — |")


if __name__ == '__main__':
    main()
