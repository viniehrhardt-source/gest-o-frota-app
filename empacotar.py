import os

# Nome do arquivo final que será gerado
ARQUIVO_SAIDA = "codigo_completo_projeto.txt"

# Extensões que você quer incluir
EXTENSOES_VALIDAS = [".py", ".html", ".css"]

# Pastas para ignorar
PASTAS_IGNORADAS = [".git", "venv", "__pycache__", ".streamlit"]

with open(ARQUIVO_SAIDA, "w", encoding="utf-8") as outfile:
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in PASTAS_IGNORADAS]
        for file in files:
            if any(file.endswith(ext) for ext in EXTENSOES_VALIDAS) and file != "empacotar.py":
                caminho_completo = os.path.join(root, file)
                outfile.write(f"\n{'='*50}\n")
                outfile.write(f"ARQUIVO: {caminho_completo}\n")
                outfile.write(f"{'='*50}\n\n")
                try:
                    with open(caminho_completo, "r", encoding="utf-8") as infile:
                        outfile.write(infile.read())
                        outfile.write("\n")
                except Exception as e:
                    outfile.write(f"Erro ao ler arquivo: {e}\n")

print(f"Projeto empacotado com sucesso em '{ARQUIVO_SAIDA}'!")
