import json
import os
import sys
import time
import threading
import ctypes
from ctypes import wintypes
import hashlib
import base64
import urllib.request
import urllib.parse
import subprocess
import tkinter as tk
from tkinter import messagebox, simpledialog, filedialog
import pyperclip
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

try:
    import keyboard
except ImportError:
    keyboard = None

# ============================================================================
#  CONFIGURAÇÕES DE VERSÃO E REPOSITÓRIO GITHUB
# ============================================================================
VERSAO_ATUAL = "v1.0.0"
GITHUB_REPO_USER = "Henrique202526"
GITHUB_REPO_NAME = "omnipad"

# ============================================================================
#  CAMINHOS — sempre ao lado do programa (.py ou .exe)
# ============================================================================
BASE_DIR = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__))
CONFIG_CREDS   = os.path.join(BASE_DIR, "credenciais_auto.json")
CONFIG_SCRIPTS = os.path.join(BASE_DIR, "scripts_auto.json")
CONFIG_UI      = os.path.join(BASE_DIR, "config_ui.json")
ARQ_ICONE      = os.path.join(BASE_DIR, "imagem.ico")
CONFIG_ACESSO  = os.path.join(BASE_DIR, "acesso.json")

# ============================================================================
#  TEMAS
# ============================================================================
TEMAS = {
    "Midnight": {
        "bg": "#0b1220", "card": "#131c2e", "card_hover": "#1b2740", "header": "#0f1626",
        "text": "#e6edf7", "sub": "#8b9bb4", "accent": "#3b82f6", "accent_hover": "#2563eb",
        "secondary": "#60a5fa", "border": "#1e293b"
    },
    "Ocean": {
        "bg": "#07212b", "card": "#0d2f3d", "card_hover": "#123d4e", "header": "#082733",
        "text": "#e0f7fa", "sub": "#7fb3c0", "accent": "#06b6d4", "accent_hover": "#0891b2",
        "secondary": "#22d3ee", "border": "#134e5e"
    },
    "Emerald": {
        "bg": "#06231a", "card": "#0b3629", "card_hover": "#114737", "header": "#072a20",
        "text": "#e3f5ee", "sub": "#7fb3a0", "accent": "#10b981", "accent_hover": "#059669",
        "secondary": "#34d399", "border": "#14523f"
    },
    "Crimson": {
        "bg": "#1c0b10", "card": "#2a121a", "card_hover": "#3a1823", "header": "#230d14",
        "text": "#fbe9ee", "sub": "#b98a96", "accent": "#ef4444", "accent_hover": "#dc2626",
        "secondary": "#f87171", "border": "#3d1721"
    },
    "Amethyst": {
        "bg": "#140b24", "card": "#1f1136", "card_hover": "#2b1849", "header": "#180d2b",
        "text": "#f0e9fb", "sub": "#9d8ab8", "accent": "#8b5cf6", "accent_hover": "#7c3aed",
        "secondary": "#a78bfa", "border": "#2e1b4d"
    },
    "Light": {
        "bg": "#f1f5f9", "card": "#ffffff", "card_hover": "#eef2f7", "header": "#e2e8f0",
        "text": "#0f172a", "sub": "#64748b", "accent": "#2563eb", "accent_hover": "#1d4ed8",
        "secondary": "#3b82f6", "border": "#cbd5e1"
    },
}

TEMA_PADRAO = "Midnight"

# ============================================================================
#  CRIPTOGRAFIA (DPAPI)
# ============================================================================
class _DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _dpapi_criptografar(dados):
    buf = ctypes.create_string_buffer(dados)
    entrada = _DATA_BLOB(len(dados), ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte)))
    saida = _DATA_BLOB()
    if not ctypes.windll.crypt32.CryptProtectData(ctypes.byref(entrada), None, None, None, None, 0, ctypes.byref(saida)):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(saida.pbData, saida.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(saida.pbData)


def _dpapi_descriptografar(dados):
    buf = ctypes.create_string_buffer(dados)
    entrada = _DATA_BLOB(len(dados), ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte)))
    saida = _DATA_BLOB()
    if not ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(entrada), None, None, None, None, 0, ctypes.byref(saida)):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(saida.pbData, saida.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(saida.pbData)


def ler_senha_hash():
    """Retorna a hash da senha salva ou None se nenhuma senha tiver sido criada ainda."""
    try:
        if os.path.exists(CONFIG_ACESSO):
            with open(CONFIG_ACESSO, "r", encoding="utf-8") as f:
                return json.load(f).get("senha_hash")
    except Exception:
        pass
    return None


def salvar_senha_hash(h):
    try:
        with open(CONFIG_ACESSO, "w", encoding="utf-8") as f:
            json.dump({"senha_hash": h}, f, indent=4)
    except Exception:
        pass


def _chave_de_senha(senha, salt):
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=200000)
    return base64.urlsafe_b64encode(kdf.derive(senha.encode("utf-8")))


def centralizar_janela(janela, largura, altura):
    janela.update_idletasks()
    largura_tela = janela.winfo_screenwidth()
    altura_tela = janela.winfo_screenheight()
    x = (largura_tela - largura) // 2
    y = (altura_tela - altura) // 2
    janela.geometry(f"{largura}x{altura}+{x}+{y}")


class AutoLoginApp:
    def __init__(self, root):
        self.root = root
        self.root.title("OmniPad")
        
        self.root.overrideredirect(True)
        
        self.config_ui = self.carregar_config_ui()
        self.tema_atual = self.config_ui.get("tema", TEMA_PADRAO)
        self.apelido_usuario = self.config_ui.get("apelido", "Usuário")
        if self.tema_atual not in TEMAS:
            self.tema_atual = TEMA_PADRAO

        largura, altura = 400, 430
        pos = self.config_ui.get("posicao")
        
        if pos and isinstance(pos, str):
            self.root.geometry(f"{largura}x{altura}{pos}")
        else:
            largura_tela = self.root.winfo_screenwidth()
            altura_tela = self.root.winfo_screenheight()
            x = (largura_tela - largura) // 2
            y = (altura_tela - altura) // 2
            self.root.geometry(f"{largura}x{altura}+{x}+{y}")

        self.root.resizable(False, True)
        self.root.protocol("WM_DELETE_WINDOW", self.ao_fechar)

        self.aba_atual = "senhas"
        # Inicia totalmente limpo sem itens de exemplo
        self.credenciais, c_texto = self.carregar_json(CONFIG_CREDS, [])
        self.scripts, s_texto = self.carregar_json(CONFIG_SCRIPTS, [])

        if c_texto or s_texto:
            self.salvar_dados()

        self.main_container = tk.Frame(root, highlightbackground=TEMAS[self.tema_atual]["border"], highlightthickness=1)
        self.main_container.pack(fill="both", expand=True)

        self.criar_componentes()

        self.root.after(100, self.aplicar_bordas_arredondadas)

        self.meu_pid = os.getpid()
        self.ultima_janela = None
        self.root.update_idletasks()
        
        threading.Thread(target=self._inicializar_background, daemon=True).start()
        threading.Thread(target=self._loop_presenca_online, daemon=True).start()

    def aplicar_bordas_arredondadas(self):
        try:
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            if not hwnd:
                hwnd = self.root.winfo_id()
            DWMWA_WINDOW_CORNER_PREFERENCE = 33
            DWMWCP_ROUND = 2
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 
                DWMWA_WINDOW_CORNER_PREFERENCE, 
                ctypes.byref(ctypes.c_int(DWMWCP_ROUND)), 
                ctypes.sizeof(ctypes.c_int)
            )
        except Exception:
            pass

    def _inicializar_background(self):
        self.registrar_atalhos_ativos()
        while True:
            try:
                hwnd = ctypes.windll.user32.GetForegroundWindow()
                if hwnd:
                    pid = wintypes.DWORD()
                    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    if pid.value != self.meu_pid:
                        self.ultima_janela = hwnd
            except Exception:
                pass
            time.sleep(0.15)

    def _loop_presenca_online(self):
        while True:
            try:
                self.enviar_ping_presenca()
            except Exception:
                pass
            time.sleep(30)

    def enviar_ping_presenca(self):
        data = json.dumps({
            "usuario": self.apelido_usuario,
            "v": VERSAO_ATUAL,
            "ts": int(time.time())
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://httpbin.org/post",
            data=data,
            headers={"Content-Type": "application/json", "User-Agent": "OmniPad-Client"}
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                pass
        except Exception:
            pass

    def carregar_json(self, arquivo, padrao):
        if not os.path.exists(arquivo):
            return padrao, False
        try:
            with open(arquivo, "rb") as f:
                raw = f.read()
        except Exception:
            return padrao, False

        try:
            return json.loads(_dpapi_descriptografar(raw).decode("utf-8")), False
        except Exception:
            pass

        try:
            return json.loads(raw.decode("utf-8")), True
        except Exception:
            pass

        return padrao, False

    def salvar_dados(self):
        self._salvar_json(CONFIG_CREDS, self.credenciais)
        self._salvar_json(CONFIG_SCRIPTS, self.scripts)

    def _salvar_json(self, arquivo, dados):
        texto = json.dumps(dados, indent=4, ensure_ascii=False).encode("utf-8")
        try:
            with open(arquivo, "wb") as f:
                f.write(_dpapi_criptografar(texto))
        except Exception:
            with open(arquivo, "w", encoding="utf-8") as f:
                json.dump(dados, f, indent=4, ensure_ascii=False)

    def exportar_dados(self, parent=None):
        parent = parent or self.root
        caminho = filedialog.asksaveasfilename(
            parent=parent, title="Exportar dados do OmniPad",
            defaultextension=".omnibak", initialfile="omnipad_backup.omnibak",
            filetypes=[("Backup OmniPad", "*.omnibak"), ("Todos os arquivos", "*.*")]
        )
        if not caminho:
            return
        pwd = simpledialog.askstring("Exportar", "Crie uma senha para o arquivo:", show="*", parent=parent)
        if not pwd:
            return
        pwd2 = simpledialog.askstring("Exportar", "Repita a senha:", show="*", parent=parent)
        if pwd != pwd2:
            messagebox.showerror("Erro", "As senhas não conferem.", parent=parent)
            return
        dados = {"credenciais": self.credenciais, "scripts": self.scripts, "tema": self.tema_atual}
        try:
            salt = os.urandom(16)
            token = Fernet(_chave_de_senha(pwd, salt)).encrypt(
                json.dumps(dados, ensure_ascii=False).encode("utf-8")
            )
            pacote = {"omni": 1, "salt": base64.b64encode(salt).decode(), "data": base64.b64encode(token).decode()}
            with open(caminho, "w", encoding="utf-8") as f:
                json.dump(pacote, f)
            messagebox.showinfo("Sucesso", "Backup exportado:\n" + caminho, parent=parent)
        except Exception as e:
            messagebox.showerror("Erro", "Falha ao exportar: " + str(e), parent=parent)

    def importar_dados(self, parent=None):
        parent = parent or self.root
        caminho = filedialog.askopenfilename(
            parent=parent, title="Importar dados do OmniPad",
            filetypes=[("Backup OmniPad", "*.omnibak"), ("Todos os arquivos", "*.*")]
        )
        if not caminho:
            return
        pwd = simpledialog.askstring("Importar", "Senha do arquivo:", show="*", parent=parent)
        if not pwd:
            return
        try:
            with open(caminho, "r", encoding="utf-8") as f:
                pacote = json.load(f)
            salt = base64.b64decode(pacote["salt"])
            token = base64.b64decode(pacote["data"])
            payload = Fernet(_chave_de_senha(pwd, salt)).decrypt(token)
            dados = json.loads(payload.decode("utf-8"))
        except Exception:
            messagebox.showerror("Erro", "Senha incorreta ou arquivo inválido.", parent=parent)
            return
        if not messagebox.askyesno("Importar", "Isso vai SUBSTITUIR os dados atuais. Continuar?", parent=parent):
            return
        self.credenciais = dados.get("credenciais", self.credenciais)
        self.scripts = dados.get("scripts", self.scripts)
        t = dados.get("tema")
        if t in TEMAS:
            self.tema_atual = t
            self.salvar_config_ui()
        self.salvar_dados()
        self.atualizar_interface()
        messagebox.showinfo("Sucesso", "Dados importados com sucesso!", parent=parent)

    def carregar_config_ui(self):
        try:
            with open(CONFIG_UI, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def salvar_config_ui(self):
        try:
            geo = self.root.geometry()
            partes = geo.split("+")
            if len(partes) >= 3:
                pos_str = f"+{partes[1]}+{partes[2]}"
            else:
                pos_str = ""

            dados = {
                "tema": self.tema_atual,
                "posicao": pos_str,
                "apelido": self.apelido_usuario
            }
            with open(CONFIG_UI, "w", encoding="utf-8") as f:
                json.dump(dados, f, indent=4, ensure_ascii=False)
        except Exception:
            pass

    def ao_fechar(self):
        self.salvar_config_ui()
        if keyboard:
            try:
                keyboard.unhook_all()
            except Exception:
                pass
        self.root.destroy()

    def aplicar_tema(self, nome_tema):
        if nome_tema in TEMAS:
            self.tema_atual = nome_tema
            self.salvar_config_ui()
            self.criar_componentes()

    def criar_componentes(self):
        for widget in self.main_container.winfo_children():
            widget.destroy()

        tema = TEMAS[self.tema_atual]
        self.main_container.configure(bg=tema["bg"], highlightbackground=tema["border"])
        self.root.configure(bg=tema["bg"])

        # ----- CABEÇALHO -----
        header = tk.Frame(self.main_container, bg=tema["header"], cursor="fleur")
        header.pack(fill="x")

        def iniciar_arraste(event):
            self._x_arraste = event.x
            self._y_arraste = event.y

        def em_arraste(event):
            x = self.root.winfo_x() + (event.x - self._x_arraste)
            y = self.root.winfo_y() + (event.y - self._y_arraste)
            self.root.geometry(f"+{x}+{y}")

        header.bind("<Button-1>", iniciar_arraste)
        header.bind("<B1-Motion>", em_arraste)

        btn_fechar = tk.Button(header, text="✕", command=self.ao_fechar, bd=0, relief="flat",
                               bg=tema["header"], fg=tema["sub"], font=("Segoe UI", 9, "bold"),
                               activebackground="#ef4444", activeforeground="white", padx=8, pady=4)
        btn_fechar.pack(side="right", padx=(0, 2), pady=2)

        lbl_titulo = tk.Label(header, text="⚡  OmniPad", bg=tema["header"], fg=tema["text"],
                              font=("Segoe UI Semibold", 11), anchor="w")
        lbl_titulo.pack(side="left", padx=12, pady=(8, 0))
        lbl_titulo.bind("<Button-1>", iniciar_arraste)
        lbl_titulo.bind("<B1-Motion>", em_arraste)

        lbl_sub = tk.Label(header, text="Clique para colar no campo selecionado", bg=tema["header"], fg=tema["sub"],
                           font=("Segoe UI", 8), anchor="w")
        lbl_sub.pack(fill="x", padx=12, pady=(0, 8))
        lbl_sub.bind("<Button-1>", iniciar_arraste)
        lbl_sub.bind("<B1-Motion>", em_arraste)

        # ----- ABAS NORMAIS -----
        barra = tk.Frame(self.main_container, bg=tema["bg"])
        barra.pack(fill="x", padx=8, pady=(8, 4))

        def botao_aba(texto, ativo, comando):
            return tk.Button(
                barra, text=texto, command=comando, bd=0, relief="flat", cursor="hand2",
                font=("Segoe UI", 8, "bold"),
                bg=(tema["accent"] if ativo else tema["card"]),
                fg=("white" if ativo else tema["text"]),
                activebackground=tema["accent_hover"], activeforeground="white",
                padx=12, pady=5
            )

        botao_aba("🔑 Senhas", self.aba_atual == "senhas", lambda: self.trocar_aba("senhas")).pack(side="left", padx=(0, 4))
        botao_aba("📝 Notas", self.aba_atual == "scripts", lambda: self.trocar_aba("scripts")).pack(side="left")

        def botao_icone(texto, comando, fundo):
            return tk.Button(barra, text=texto, command=comando, bd=0, relief="flat", cursor="hand2",
                             font=("Segoe UI", 8, "bold"), bg=fundo, fg="white",
                             activebackground=tema["accent_hover"], activeforeground="white",
                             padx=6, pady=5)

        botao_icone("＋ Novo", self.adicionar_item, "#059669").pack(side="right", padx=(4, 0))
        botao_icone("⚙️", self.abrir_gerenciador, tema["card"]).pack(side="right", padx=(4, 0))
        botao_icone("🎨", self.menu_temas, tema["card"]).pack(side="right")

        # ----- ÁREA DE CARDS (rolável) -----
        area = tk.Frame(self.main_container, bg=tema["bg"])
        area.pack(fill="both", expand=True, padx=6, pady=4)

        self.canvas = tk.Canvas(area, bg=tema["bg"], highlightthickness=0)
        self.scrollbar = tk.Scrollbar(area, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg=tema["bg"])

        self.scrollable_frame.bind(
            "<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self.canvas_window, width=e.width))

        def _on_mouse_wheel(event):
            if event.delta:
                self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            elif event.num == 4:
                self.canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                self.canvas.yview_scroll(1, "units")

        self.canvas.bind_all("<MouseWheel>", _on_mouse_wheel)
        self.canvas.bind_all("<Button-4>", _on_mouse_wheel)
        self.canvas.bind_all("<Button-5>", _on_mouse_wheel)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # ----- RODAPÉ -----
        tk.Label(self.main_container,
                 text=("Notas: clique para colar"
                       if self.aba_atual == "scripts"
                       else "Senhas: atalhos (F1, F2…)  •  Clique cola"),
                 bg=tema["bg"], fg=tema["sub"], font=("Segoe UI", 7, "bold")).pack(fill="x", pady=(2, 6))

        self.atualizar_interface()

    def trocar_aba(self, aba):
        self.aba_atual = aba
        self.criar_componentes()

    def menu_temas(self):
        tema = TEMAS[self.tema_atual]
        win = tk.Toplevel(self.root)
        win.title("Estilo")
        win.attributes("-topmost", True)
        win.configure(bg=tema["bg"])
        win.resizable(False, False)
        self._centralizar_sobre(win, 240, 300)

        tk.Label(win, text="Escolher Tema", fg=tema["text"], bg=tema["bg"],
                 font=("Segoe UI", 10, "bold")).pack(pady=12)

        for nome in TEMAS:
            t = TEMAS[nome]
            ativo = (nome == self.tema_atual)
            tk.Button(win, text=("✔ " if ativo else "    ") + nome,
                      bg=(t["accent"] if ativo else t["card"]),
                      fg="white", font=("Segoe UI", 8, "bold"), bd=0, relief="flat",
                      cursor="hand2", activebackground=t["accent_hover"], activeforeground="white",
                      command=lambda n=nome: [self.aplicar_tema(n), win.destroy()]
                      ).pack(fill="x", padx=16, pady=3)

    def atualizar_interface(self):
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        tema = TEMAS[self.tema_atual]
        self.scrollable_frame.configure(bg=tema["bg"])
        self.canvas.configure(bg=tema["bg"])

        lista_ativa = self.credenciais if self.aba_atual == "senhas" else self.scripts

        if not lista_ativa:
            msg = "Nenhuma senha salva." if self.aba_atual == "senhas" else "Nenhuma nota salva."
            tk.Label(self.scrollable_frame, text=f"{msg}\nClique em ＋ Novo.",
                     fg=tema["sub"], bg=tema["bg"], font=("Segoe UI", 8, "bold"), justify="center").pack(pady=35)
            return

        for i in range(0, len(lista_ativa), 2):
            linha = tk.Frame(self.scrollable_frame, bg=tema["bg"])
            linha.pack(fill="x", pady=3, padx=3)

            c1 = self._criar_card(linha, lista_ativa[i], tema)
            c1.pack(side="left", padx=3, expand=True, fill="both")

            if i + 1 < len(lista_ativa):
                c2 = self._criar_card(linha, lista_ativa[i + 1], tema)
                c2.pack(side="right", padx=3, expand=True, fill="both")

    def _criar_card(self, master, item, tema):
        card = tk.Frame(master, bg=tema["card"], bd=0,
                        highlightbackground=tema["border"], highlightthickness=1, cursor="hand2")
        self.preencher_conteudo_card(card, item, tema)
        return card

    def preencher_conteudo_card(self, card, item, tema):
        if self.aba_atual == "senhas":
            atalho = item.get("atalho", "").strip()
            info = f"⚡ [{atalho.upper()}]" if atalho else "🖱️ Clique para colar"
        else:
            info = "🖱️ Clique para colar"

        lbl_nome = tk.Label(card, text=item["nome"], fg=tema["text"], bg=tema["card"],
                            font=("Segoe UI", 8, "bold"), anchor="w", justify="left",
                            wraplength=150, cursor="hand2")
        lbl_nome.pack(fill="x", padx=10, pady=(8, 2))

        lbl_info = tk.Label(card, text=info, fg=tema["secondary"], bg=tema["card"],
                            font=("Segoe UI", 7, "bold"), anchor="w", cursor="hand2")
        lbl_info.pack(fill="x", padx=10, pady=(0, 8))

        for w in (card, lbl_nome, lbl_info):
            w.bind("<Button-1>", lambda e, i=item: self.executar_acao(i))

        def entrar(_e=None):
            card.configure(bg=tema["card_hover"], highlightbackground=tema["accent"])
            lbl_nome.configure(bg=tema["card_hover"])
            lbl_info.configure(bg=tema["card_hover"])

        def sair(_e=None):
            card.configure(bg=tema["card"], highlightbackground=tema["border"])
            lbl_nome.configure(bg=tema["card"])
            lbl_info.configure(bg=tema["card"])

        for w in (card, lbl_nome, lbl_info):
            w.bind("<Enter>", entrar)
            w.bind("<Leave>", sair)

    def executar_acao(self, item):
        try:
            fg = ctypes.windll.user32.GetForegroundWindow()
            if fg:
                pid = wintypes.DWORD()
                ctypes.windll.user32.GetWindowThreadProcessId(fg, ctypes.byref(pid))
                if pid.value == self.meu_pid and self.ultima_janela:
                    self._focar_janela(self.ultima_janela)
                    time.sleep(0.15)
        except Exception:
            pass

        if self.aba_atual == "senhas":
            usr = item.get("usuario", "")
            pwd = item.get("senha", "")
            if usr:
                pyperclip.copy(usr)
                time.sleep(0.04)
                if keyboard: keyboard.send("ctrl+v")
                time.sleep(0.06)
                if keyboard: keyboard.send("tab")
                time.sleep(0.06)
            if pwd:
                pyperclip.copy(pwd)
                time.sleep(0.04)
                if keyboard: keyboard.send("ctrl+v")
        else:
            conteudo = item.get("conteudo", "")
            if conteudo:
                pyperclip.copy(conteudo)
                time.sleep(0.04)
                if keyboard: keyboard.send("ctrl+v")

    def registrar_atalhos_ativos(self):
        if not keyboard:
            return
        try:
            keyboard.unhook_all()
        except Exception:
            pass

        for item in self.credenciais:
            atalho = item.get("atalho", "").strip().lower()
            atalho = atalho.replace("control", "ctrl").replace(" ", "")
            if atalho:
                try:
                    keyboard.add_hotkey(atalho, lambda i=item: self.executar_acao(i), suppress=False)
                except Exception as e:
                    print(f"Erro ao registrar atalho '{atalho}': {e}")

    def adicionar_item(self):
        if self.aba_atual == "senhas":
            nome = simpledialog.askstring("Novo", "Título:", parent=self.root)
            if not nome: return
            usuario = simpledialog.askstring("Novo", "Usuário (Vazio se for só senha):", parent=self.root)
            if usuario is None: return
            senha = simpledialog.askstring("Novo", "Senha:", show="*", parent=self.root)
            if senha is None: return
            atalho = simpledialog.askstring("Novo", "Tecla de Atalho (Opcional - ex: f1, ctrl+shift+q):", parent=self.root)
            if atalho is None: return
            self.credenciais.append({
                "nome": nome.strip(), "usuario": usuario.strip(), "senha": senha,
                "atalho": atalho.strip().lower()
            })
        else:
            self.abrir_janela_nota()
            return

        self.salvar_dados()
        self.atualizar_interface()

    def abrir_janela_nota(self, item_para_editar=None, indice_editar=None):
        tema = TEMAS[self.tema_atual]
        janela_nota = tk.Toplevel(self.root)
        janela_nota.title("Nova Nota" if item_para_editar is None else "Editar Nota")
        janela_nota.attributes("-topmost", True)
        janela_nota.configure(bg=tema["bg"])
        janela_nota.resizable(False, False)
        self._centralizar_sobre(janela_nota, 380, 320)

        tk.Label(janela_nota, text="Título da Nota:", fg=tema["text"], bg=tema["bg"],
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=16, pady=(12, 4))
        
        entry_titulo = tk.Entry(janela_nota, font=("Segoe UI", 10),
                                bg=tema["card"], fg=tema["text"], insertbackground=tema["text"],
                                bd=0, relief="flat", highlightbackground=tema["border"], highlightthickness=1)
        entry_titulo.pack(fill="x", padx=16, pady=(0, 10), ipady=4)

        tk.Label(janela_nota, text="Conteúdo da Nota:", fg=tema["text"], bg=tema["bg"],
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=16, pady=(0, 4))

        text_conteudo = tk.Text(janela_nota, font=("Segoe UI", 9), height=6,
                                bg=tema["card"], fg=tema["text"], insertbackground=tema["text"],
                                bd=0, relief="flat", highlightbackground=tema["border"], highlightthickness=1)
        text_conteudo.pack(fill="both", expand=True, padx=16, pady=(0, 14))

        if item_para_editar:
            entry_titulo.insert(0, item_para_editar.get("nome", ""))
            text_conteudo.insert("1.0", item_para_editar.get("conteudo", ""))

        entry_titulo.focus()

        def salvar():
            titulo = entry_titulo.get().strip()
            conteudo = text_conteudo.get("1.0", tk.END).strip()
            if not titulo or not conteudo:
                messagebox.showwarning("Aviso", "Preencha o título e o conteúdo da nota.", parent=janela_nota)
                return

            if item_para_editar is not None and indice_editar is not None:
                self.scripts[indice_editar] = {"nome": titulo, "conteudo": conteudo, "atalho": ""}
            else:
                self.scripts.append({"nome": titulo, "conteudo": conteudo, "atalho": ""})

            self.salvar_dados()
            self.atualizar_interface()
            janela_nota.destroy()

        tk.Button(janela_nota, text="💾 Salvar Nota", bg=tema["accent"], fg="white",
                  font=("Segoe UI", 9, "bold"), bd=0, relief="flat", cursor="hand2",
                  activebackground=tema["accent_hover"], activeforeground="white",
                  command=salvar).pack(fill="x", padx=16, pady=(0, 12), ipady=4)

    def abrir_gerenciador(self):
        tema = TEMAS[self.tema_atual]
        ger = tk.Toplevel(self.root)
        ger.title("Configurações e Gerenciamento")
        ger.configure(bg=tema["bg"])
        ger.resizable(False, False)
        self._centralizar_sobre(ger, 360, 520)

        lista_ativa = self.credenciais if self.aba_atual == "senhas" else self.scripts

        tk.Label(ger, text=f"Gerenciar { 'Senhas' if self.aba_atual == 'senhas' else 'Notas' }:", fg=tema["text"],
                 bg=tema["bg"], font=("Segoe UI", 9, "bold")).pack(pady=8)

        lb = tk.Listbox(ger, bg=tema["card"], fg=tema["text"], font=("Segoe UI", 8),
                        selectbackground=tema["accent"], bd=0, highlightthickness=0)
        lb.pack(fill="both", expand=True, padx=12, pady=4)

        def recarregar_listbox():
            lb.delete(0, tk.END)
            for c in lista_ativa:
                if self.aba_atual == "senhas":
                    alt = c.get('atalho','')
                    extra = f"[{alt.upper()}]" if alt else "[clique]"
                else:
                    extra = "clique p/ colar"
                lb.insert(tk.END, f"{c['nome']}   {extra}")

        recarregar_listbox()

        def editar_selecionado():
            sel = lb.curselection()
            if not sel:
                messagebox.showwarning("Aviso", "Selecione um item para editar.", parent=ger)
                return
            idx = sel[0]
            item = lista_ativa[idx]

            if self.aba_atual == "senhas":
                novo_nome = simpledialog.askstring("Editar", "Título:", initialvalue=item["nome"], parent=ger)
                if not novo_nome: return
                item["nome"] = novo_nome.strip()

                novo_usr = simpledialog.askstring("Editar", "Usuário:", initialvalue=item.get("usuario", ""), parent=ger)
                if novo_usr is not None: item["usuario"] = novo_usr.strip()
                nova_pwd = simpledialog.askstring("Editar", "Senha:", initialvalue=item.get("senha", ""), show="*", parent=ger)
                if nova_pwd is not None: item["senha"] = nova_pwd
                novo_alt = simpledialog.askstring("Editar", "Atalho (Opcional):", initialvalue=item.get("atalho", ""), parent=ger)
                if novo_alt is not None: item["atalho"] = novo_alt.strip().lower()

                self.salvar_dados()
                self.atualizar_interface()
                recarregar_listbox()
                messagebox.showinfo("Sucesso", "Registro atualizado!", parent=ger)
            else:
                ger.destroy()
                self.abrir_janela_nota(item_para_editar=item, indice_editar=idx)

        def excluir_selecionado():
            sel = lb.curselection()
            if not sel:
                messagebox.showwarning("Aviso", "Selecione um item para excluir.", parent=ger)
                return
            idx = sel[0]
            item = lista_ativa[idx]
            if not messagebox.askyesno("Excluir", f"Excluir '{item['nome']}'?\nEssa ação não pode ser desfeita.", parent=ger):
                return
            lista_ativa.pop(idx)
            self.salvar_dados()
            self.atualizar_interface()
            recarregar_listbox()

        tk.Button(ger, text="✏️ Editar Selecionado", bg="#2563eb", fg="white",
                  font=("Segoe UI", 8, "bold"), bd=0, relief="flat", cursor="hand2",
                  activebackground="#1d4ed8", activeforeground="white",
                  command=editar_selecionado).pack(fill="x", padx=12, pady=(4, 2))

        tk.Button(ger, text="🗑️ Excluir Selecionado", bg="#ef4444", fg="white",
                  font=("Segoe UI", 8, "bold"), bd=0, relief="flat", cursor="hand2",
                  activebackground="#dc2626", activeforeground="white",
                  command=excluir_selecionado).pack(fill="x", padx=12, pady=(0, 6))

        frame_rede = tk.Frame(ger, bg=tema["bg"])
        frame_rede.pack(fill="x", padx=12, pady=(4, 6))

        def checar_atualizacao():
            threading.Thread(target=lambda: self.verificar_atualizacao_github(ger), daemon=True).start()

        tk.Button(frame_rede, text="🔄 Buscar Atualizações", bg=tema["card"], fg=tema["text"],
                  font=("Segoe UI", 8, "bold"), bd=0, relief="flat", cursor="hand2",
                  activebackground=tema["accent"], activeforeground="white",
                  command=checar_atualizacao).pack(side="left", fill="x", expand=True, padx=(0, 2))

        def alterar_apelido():
            novo = simpledialog.askstring("Meu Apelido", "Seu nome/apelido no OmniPad:", initialvalue=self.apelido_usuario, parent=ger)
            if novo and novo.strip():
                self.apelido_usuario = novo.strip()
                self.salvar_config_ui()
                messagebox.showinfo("Sucesso", "Apelido atualizado!", parent=ger)

        tk.Button(frame_rede, text="👤 Meu Apelido", bg=tema["card"], fg=tema["text"],
                  font=("Segoe UI", 8, "bold"), bd=0, relief="flat", cursor="hand2",
                  activebackground=tema["accent"], activeforeground="white",
                  command=alterar_apelido).pack(side="right", fill="x", expand=True, padx=(2, 0))

        frame_exp = tk.Frame(ger, bg=tema["bg"])
        frame_exp.pack(fill="x", padx=12, pady=(0, 6))
        tk.Button(frame_exp, text="📤 Exportar", bg=tema["card"], fg=tema["text"],
                  font=("Segoe UI", 8, "bold"), bd=0, relief="flat", cursor="hand2",
                  activebackground=tema["accent"], activeforeground="white",
                  command=lambda: self.exportar_dados(ger)).pack(side="left", fill="x", expand=True, padx=(0, 4))
        tk.Button(frame_exp, text="📥 Importar", bg=tema["card"], fg=tema["text"],
                  font=("Segoe UI", 8, "bold"), bd=0, relief="flat", cursor="hand2",
                  activebackground=tema["accent"], activeforeground="white",
                  command=lambda: self.importar_dados(ger)).pack(side="right", fill="x", expand=True, padx=(4, 0))

        def gerenciar_senha_acesso():
            senha_atual_hash = ler_senha_hash()
            if senha_atual_hash:
                atual = simpledialog.askstring("Senha de Acesso", "Senha atual (deixe vazio se quiser remover a senha):", show="*", parent=ger)
                if atual is None:
                    return
                if hashlib.sha256(atual.encode("utf-8")).hexdigest() != senha_atual_hash:
                    messagebox.showerror("Erro", "Senha atual incorreta.", parent=ger)
                    return
            
            nova = simpledialog.askstring("Senha de Acesso", "Nova senha (ou deixe em branco para remover):", show="*", parent=ger)
            if nova is None:
                return
            
            if nova.strip() == "":
                salvar_senha_hash("")
                messagebox.showinfo("Sucesso", "Proteção por senha removida! O app abrirá direto.", parent=ger)
            else:
                conf = simpledialog.askstring("Senha de Acesso", "Confirme a nova senha:", show="*", parent=ger)
                if nova != conf:
                    messagebox.showerror("Erro", "As senhas não conferem.", parent=ger)
                    return
                salvar_senha_hash(hashlib.sha256(nova.encode("utf-8")).hexdigest())
                messagebox.showinfo("Sucesso", "Senha de acesso definida com sucesso!", parent=ger)

        lbl_btn_senha = "🔑 Alterar / Remover Senha" if ler_senha_hash() else "🔑 Criar Senha de Entrada"
        tk.Button(ger, text=lbl_btn_senha, bg=tema["card"], fg=tema["text"],
                  font=("Segoe UI", 8, "bold"), bd=0, relief="flat", cursor="hand2",
                  activebackground=tema["accent"], activeforeground="white",
                  command=gerenciar_senha_acesso).pack(fill="x", padx=12, pady=(0, 8))

    def verificar_atualizacao_github(self, parent_win=None):
        url_releases = f"https://api.github.com/repos/{GITHUB_REPO_USER}/{GITHUB_REPO_NAME}/releases/latest"
        req = urllib.request.Request(url_releases, headers={"User-Agent": "OmniPad-Updater"})
        try:
            with urllib.request.urlopen(req, timeout=6) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode())
                    tag_online = data.get("tag_name", "")
                    if tag_online and tag_online != VERSAO_ATUAL:
                        if messagebox.askyesno("Atualização Encontrada",
                                               f"Nova versão {tag_online} disponível! (Versão atual: {VERSAO_ATUAL})\n\nDeseja atualizar agora?", parent=parent_win):
                            assets = data.get("assets", [])
                            for asset in assets:
                                if asset.get("name", "").endswith(".exe"):
                                    download_url = asset.get("browser_download_url")
                                    self._baixar_e_substituir_exe(download_url)
                                    return
                            messagebox.showinfo("Aviso", "Nova versão encontrada, mas o arquivo .exe não está disponível nas releases.", parent=parent_win)
                    else:
                        messagebox.showinfo("OmniPad", f"Você já está executando a versão mais recente ({VERSAO_ATUAL}).", parent=parent_win)
        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível verificar atualizações no momento.\n({e})", parent=parent_win)

    def _baixar_e_substituir_exe(self, url):
        try:
            exe_novo = os.path.join(BASE_DIR, "omnipad_novo.exe")
            urllib.request.urlretrieve(url, exe_novo)
            
            bat_script = os.path.join(BASE_DIR, "update.bat")
            with open(bat_script, "w") as f:
                f.write(f'''@echo off
timeout /t 2 /nobreak > nul
move /y "{exe_novo}" "{sys.executable}"
start "" "{sys.executable}"
del "%~f0"
''')
            subprocess.Popen([bat_script], shell=True)
            self.ao_fechar()
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao realizar download da atualização:\n{e}")

    def _focar_janela(self, hwnd):
        try:
            ctypes.windll.user32.ShowWindow(hwnd, 9)
            ctypes.windll.user32.SetForegroundWindow(hwnd)
        except Exception:
            pass

    def _centralizar_sobre(self, popup, largura, altura):
        try:
            self.root.update_idletasks()
            px = self.root.winfo_rootx()
            py = self.root.winfo_rooty()
            pw = self.root.winfo_width()
            ph = self.root.winfo_height()
            x = px + (pw - largura) // 2
            y = py + (ph - altura) // 2
            popup.geometry(f"{largura}x{altura}+{x}+{y}")
        except Exception:
            popup.geometry(f"{largura}x{altura}")


def iniciar_aplicacao():
    app_root = tk.Tk()
    AutoLoginApp(app_root)
    app_root.mainloop()


def tela_login():
    senha_salva_hash = ler_senha_hash()
    
    # Se não houver senha definida, entra direto no OmniPad
    if not senha_salva_hash:
        iniciar_aplicacao()
        return

    root = tk.Tk()
    root.title("OmniPad")
    
    centralizar_janela(root, 300, 170)
    root.resizable(False, False)

    try:
        if hasattr(sys, '_MEIPASS'):
            caminho_icone = os.path.join(sys._MEIPASS, "imagem.ico")
        else:
            caminho_icone = ARQ_ICONE
        if os.path.exists(caminho_icone):
            root.iconbitmap(caminho_icone)
    except Exception:
        pass

    tema = TEMAS[TEMA_PADRAO]
    root.configure(bg=tema["bg"])

    tk.Label(root, text="🔒 Acesso Restrito", bg=tema["bg"], fg=tema["text"],
             font=("Segoe UI", 10, "bold")).pack(pady=(15, 3))
    tk.Label(root, text="Senha de acesso:", bg=tema["bg"], fg=tema["sub"],
             font=("Segoe UI", 8)).pack(pady=(0, 8))

    entry_senha = tk.Entry(root, show="*", font=("Segoe UI", 10), justify="center",
                           bg=tema["card"], fg=tema["text"], insertbackground=tema["text"],
                           bd=0, relief="flat", highlightbackground=tema["border"], highlightthickness=1)
    entry_senha.pack(ipadx=8, ipady=4, fill="x", padx=25, pady=4)
    entry_senha.focus()

    def verificar(_e=None):
        digitada = entry_senha.get()
        h_digitado = hashlib.sha256(digitada.encode("utf-8")).hexdigest()
        if h_digitado == ler_senha_hash():
            root.destroy()
            iniciar_aplicacao()
        else:
            messagebox.showerror("Erro", "Senha incorreta!", parent=root)
            entry_senha.delete(0, tk.END)

    entry_senha.bind("<Return>", verificar)

    tk.Button(root, text="Entrar", command=verificar, bg=tema["accent"], fg="white",
              font=("Segoe UI", 8, "bold"), bd=0, relief="flat", cursor="hand2",
              activebackground=tema["accent_hover"], activeforeground="white",
              padx=12, pady=5).pack(pady=10)

    root.mainloop()


if __name__ == "__main__":
    tela_login()