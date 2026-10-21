import os
import subprocess
import glob

files_to_compile = {
    "交底书.tex": "temp_jiaodishu",
    "检索报告.tex": "temp_jiansuobaogao"
}

latex_dir = r"c:\Users\Lenovo\patents\5_QTS-Falcon_Threshold_Signature\latex"
os.chdir(latex_dir)

# Ensure output directory exists
if not os.path.exists("output"):
    os.makedirs("output")

for filename, temp_name in files_to_compile.items():
    if os.path.exists(filename):
        print(f"Processing {filename}...")
        
        # Rename to temp ASCII name
        temp_tex = temp_name + ".tex"
        if os.path.exists(temp_tex):
            os.remove(temp_tex) # Clean up if exists
            
        os.rename(filename, temp_tex)
        
        try:
            # Compile twice
            for i in range(2):
                print(f"  Pass {i+1}...")
                result = subprocess.run(
                    ["xelatex", "-interaction=nonstopmode", "-output-directory=output", temp_tex],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                if result.returncode != 0:
                    print(f"  Warning: Pass {i+1} returned code {result.returncode}")
            
            # Check log for errors
            log_file = os.path.join("output", temp_name + ".log")
            if os.path.exists(log_file):
                with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                    log_content = f.read()
                    if "!" in log_content: # Basic check for errors
                        print("  Potential errors found in log:")
                        lines = log_content.splitlines()
                        for line in lines:
                            if line.startswith("!"):
                                print("    " + line)
            
            # Check for PDF and rename
            pdf_file = os.path.join("output", temp_name + ".pdf")
            final_pdf_name = os.path.join("output", os.path.splitext(filename)[0] + ".pdf")
            
            if os.path.exists(pdf_file):
                if os.path.exists(final_pdf_name):
                    os.remove(final_pdf_name)
                os.rename(pdf_file, final_pdf_name)
                print(f"  SUCCESS: Generated {final_pdf_name}")
            else:
                print(f"  ERROR: No PDF generated for {filename}")

        except Exception as e:
            print(f"  Exception during compilation: {e}")
            
        finally:
            # Rename back
            if os.path.exists(temp_tex):
                os.rename(temp_tex, filename)
                print(f"  Restored {filename}")
    else:
        print(f"File {filename} not found in {os.getcwd()}")
