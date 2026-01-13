import os
import subprocess

# Define the source and target files
conversions = [
    {
        "source": "交底书.tex",
        "target": "专利技术交底书.docx",
        "reference": "../专利技术交底书.docx"  # Try to use existing doc as reference if it exists, for styles
    },
    {
        "source": "检索报告.tex",
        "target": "现有技术检索报告.docx",
        "reference": "../现有技术检索报告.docx"
    }
]

latex_dir = r"c:\Users\Lenovo\patents\5_QTS-Falcon_Threshold_Signature\latex"
output_dir = r"c:\Users\Lenovo\patents\5_QTS-Falcon_Threshold_Signature\latex\output"

os.chdir(latex_dir)
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

for item in conversions:
    source_file = item["source"]
    target_file = os.path.join(output_dir, item["target"])
    
    print(f"Converting {source_file} to {target_file}...")
    
    # Check if source exists
    if not os.path.exists(source_file):
        print(f"Error: Source file {source_file} not found.")
        continue

    # Construct pandoc command
    # Using specific options for better Chinese support and reference doc if available
    cmd = ["pandoc", source_file, "-o", target_file]
    
    # Add reference doc if exists in parent or current folder to keep styles
    # We check relative to script execution
    # Actually, simpler to just run without reference first or use a known good template
    # cmd.extend(["--reference-doc=reference.docx"]) 
    
    # Add table of contents
    cmd.append("--toc")
    
    # Run pandoc
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"Successfully created {target_file}")
        else:
            print(f"Error converting {source_file}:")
            print(result.stderr)
            
    except Exception as e:
         print(f"Exception: {e}")

print("Done.")
