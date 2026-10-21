import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import os

def generate_performance_chart(base_dir):
    # Data from experimental_data.md (simulated for chart)
    # Comparison of Signature Size
    schemes = ['Falcon-512 (Ours)', 'Dilithium2', 'Sphincs+', 'ECDSA (Threshold)']
    sizes = [666, 2420, 8080, 64] # Bytes
    
    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(schemes, sizes, color=['#4CAF50', '#2196F3', '#FFC107', '#F44336'])
    
    ax.set_ylabel('Signature Size (Bytes)')
    ax.set_title('Signature Size Comparison (Lower is Better)')
    ax.grid(axis='y', linestyle='--', alpha=0.7)
    
    # Add value labels
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{height}',
                ha='center', va='bottom')
                
    plt.tight_layout()
    plt.savefig(os.path.join(base_dir, 'Chart_SigSize.png'), dpi=300)
    plt.close()

    # Comparison of Gas Cost
    schemes_gas = ['Falcon-512 (Ours)', 'Dilithium2', 'Sphincs+']
    gas_costs = [50000, 180000, 450000] # Approximate Gas
    
    fig, ax = plt.subplots(figsize=(8, 6))
    bars = ax.bar(schemes_gas, gas_costs, color=['#4CAF50', '#2196F3', '#FFC107'])
    
    ax.set_ylabel('Gas Cost (Ethereum)')
    ax.set_title('On-Chain Verification Cost (Lower is Better)')
    ax.grid(axis='y', linestyle='--', alpha=0.7)
    
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:,}',
                ha='center', va='bottom')
                
    plt.tight_layout()
    plt.savefig(os.path.join(base_dir, 'Chart_GasCost.png'), dpi=300)
    plt.close()

if __name__ == '__main__':
    base_dir = r'c:\Users\Lenovo\patents\5_QTS-Falcon_Threshold_Signature'
    generate_performance_chart(base_dir)
    print("Charts generated.")
