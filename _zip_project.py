import os
import zipfile

def zipdir(path, ziph):
    # ziph is zipfile handle
    for root, dirs, files in os.walk(path):
        # Exclude directories
        dirs[:] = [d for d in dirs if d not in ['.venv', '__pycache__', '.git', 'node_modules', '.chroma']]
        for file in files:
            if not file.endswith('.zip'):
                file_path = os.path.join(root, file)
                # Compute path inside zip file
                arcname = os.path.relpath(file_path, os.path.dirname(path))
                ziph.write(file_path, arcname)

if __name__ == '__main__':
    zipf = zipfile.ZipFile('메뉴얼_제작_백업.zip', 'w', zipfile.ZIP_DEFLATED)
    zipdir('.', zipf)
    zipf.close()
    print("압축 완료: 메뉴얼_제작_백업.zip")
