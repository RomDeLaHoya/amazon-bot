import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
import os
from datetime import datetime

TOKEN = os.getenv("DISCORD_TOKEN", "")
DB_PATH = "business.db"

# ─────────────────────────────────────────
#  COULEURS PAR CHANNEL
# ─────────────────────────────────────────
COULEURS = {
    "eligible":     0x2ecc71,   # vert
    "facture_10":   0xf1c40f,   # jaune
    "facture_100":  0xe67e22,   # orange
    "bloquee":      0xe74c3c,   # rouge
}

TITRES_CHANNEL = {
    "eligible":     "MARQUES ÉLIGIBLES",
    "facture_10":   "FACTURE REQUISE — 10 PCS",
    "facture_100":  "FACTURE REQUISE — 100 PCS",
    "bloquee":      "MARQUES BLOQUÉES",
}

# ─────────────────────────────────────────
#  DATABASE
# ─────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Table des catégories (ex: COSMÉTIQUES, JOUETS...)
    c.execute("""CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT NOT NULL,
        statut TEXT NOT NULL,          -- eligible | facture_10 | facture_100 | bloquee
        position INTEGER DEFAULT 0,
        message_id TEXT,               -- ID du message Discord épinglé
        channel_id TEXT                -- ID du channel Discord
    )""")

    # Table des marques
    c.execute("""CREATE TABLE IF NOT EXISTS marques (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT NOT NULL,
        categorie_id INTEGER NOT NULL,
        position INTEGER DEFAULT 0,
        date_ajout TEXT,
        FOREIGN KEY(categorie_id) REFERENCES categories(id)
    )""")

    # Tables existantes conservées
    c.execute("""CREATE TABLE IF NOT EXISTS magasins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT NOT NULL, ville TEXT, adresse TEXT, notes TEXT, date_ajout TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS sites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT NOT NULL, url TEXT NOT NULL,
        type TEXT DEFAULT 'grossiste', notes TEXT, date_ajout TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS produits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT NOT NULL, marque TEXT, asin TEXT,
        prix_achat REAL, prix_vente REAL, fournisseur TEXT,
        statut TEXT DEFAULT 'a_tester', notes TEXT, date_ajout TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        titre TEXT NOT NULL, contenu TEXT NOT NULL,
        categorie TEXT DEFAULT 'general', date_ajout TEXT
    )""")

    # Migration : ajout colonnes manquantes si ancienne DB
    try:
        c.execute("ALTER TABLE marques ADD COLUMN categorie_id INTEGER")
    except: pass
    try:
        c.execute("ALTER TABLE marques ADD COLUMN position INTEGER DEFAULT 0")
    except: pass
    try:
        c.execute("ALTER TABLE categories ADD COLUMN message_id TEXT")
    except: pass
    try:
        c.execute("ALTER TABLE categories ADD COLUMN channel_id TEXT")
    except: pass
    try:
        c.execute("ALTER TABLE categories ADD COLUMN position INTEGER DEFAULT 0")
    except: pass

    conn.commit()
    conn.close()

def get_db():
    return sqlite3.connect(DB_PATH)

# ─────────────────────────────────────────
#  BOT
# ─────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ─────────────────────────────────────────
#  HELPERS EMBEDS
# ─────────────────────────────────────────
def embed_ok(titre, desc=""):
    e = discord.Embed(title=f"✅  {titre}", description=desc, color=0x2ecc71)
    e.timestamp = datetime.now()
    return e

def embed_err(titre, desc=""):
    return discord.Embed(title=f"❌  {titre}", description=desc, color=0xe74c3c)

# ─────────────────────────────────────────
#  CONSTRUIRE L'EMBED D'UNE CATÉGORIE
# ─────────────────────────────────────────
def build_categorie_embed(cat_id: int, nom: str, statut: str) -> discord.Embed:
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT nom FROM marques WHERE categorie_id=? ORDER BY position ASC, id ASC", (cat_id,))
    marques = [r[0] for r in c.fetchall()]
    conn.close()

    couleur = COULEURS.get(statut, 0x95a5a6)

    separateur = "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬"
    titre = f"{separateur}\n  **{nom.upper()}**\n{separateur}"

    if marques:
        liste = "\n".join([f"  {m}" for m in marques])
    else:
        liste = "  *Aucune marque — utilise `/marque_add`*"

    e = discord.Embed(description=f"{titre}\n{liste}", color=couleur)
    e.set_footer(text=f"{len(marques)} marque(s)  •  {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    return e

# ─────────────────────────────────────────
#  METTRE À JOUR LE MESSAGE DISCORD
# ─────────────────────────────────────────
async def refresh_categorie(cat_id: int):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT nom, statut, message_id, channel_id FROM categories WHERE id=?", (cat_id,))
    row = c.fetchone()
    conn.close()
    if not row or not row[2] or not row[3]:
        return  # Pas encore de message lié

    nom, statut, message_id, channel_id = row
    try:
        channel = bot.get_channel(int(channel_id))
        if not channel:
            return
        msg = await channel.fetch_message(int(message_id))
        embed = build_categorie_embed(cat_id, nom, statut)
        await msg.edit(embed=embed)
    except Exception as e:
        print(f"⚠️ refresh_categorie erreur : {e}")

# ─────────────────────────────────────────
#  EVENTS
# ─────────────────────────────────────────
@bot.event
async def on_ready():
    init_db()
    print(f"✅ Bot connecté : {bot.user} ({bot.user.id})")
    try:
        synced = await bot.tree.sync()
        print(f"✅ {len(synced)} commandes synchronisées")
    except Exception as e:
        print(f"❌ Sync erreur : {e}")
        import traceback
        traceback.print_exc()
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.watching, name="ton business Amazon 📦"
    ))

# ══════════════════════════════════════════════════════════════
#  CATÉGORIES
# ══════════════════════════════════════════════════════════════

@bot.tree.command(name="cat_add", description="Créer une nouvelle catégorie de marques dans ce channel")
@app_commands.describe(
    nom="Nom de la catégorie (ex: COSMÉTIQUES)",
    statut="Dans quel channel poster ?"
)
@app_commands.choices(statut=[
    app_commands.Choice(name="🟢 Éligibles", value="eligible"),
    app_commands.Choice(name="🟡 Facture 10 pcs", value="facture_10"),
    app_commands.Choice(name="🟠 Facture 100 pcs", value="facture_100"),
    app_commands.Choice(name="🔴 Bloquées", value="bloquee"),
])
async def cat_add(interaction: discord.Interaction, nom: str, statut: str):
    await interaction.response.defer()

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id FROM categories WHERE LOWER(nom)=LOWER(?) AND statut=?", (nom, statut))
    if c.fetchone():
        conn.close()
        await interaction.followup.send(embed=embed_err("Catégorie existante", f"**{nom}** existe déjà dans ce groupe."), ephemeral=True)
        return

    # Calcul position
    c.execute("SELECT MAX(position) FROM categories WHERE statut=?", (statut,))
    max_pos = c.fetchone()[0] or 0

    c.execute("INSERT INTO categories (nom, statut, position) VALUES (?,?,?)",
              (nom, statut, max_pos + 1))
    cat_id = c.lastrowid
    conn.commit()
    conn.close()

    # Poster le message embed dans ce channel
    embed = build_categorie_embed(cat_id, nom, statut)
    msg = await interaction.channel.send(embed=embed)

    # Sauvegarder le message_id et channel_id
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE categories SET message_id=?, channel_id=? WHERE id=?",
              (str(msg.id), str(interaction.channel.id), cat_id))
    conn.commit()
    conn.close()

    await interaction.followup.send(embed=embed_ok("Catégorie créée", f"**{nom.upper()}** ajoutée — le message s'actualisera automatiquement."), ephemeral=True)

@bot.tree.command(name="cat_delete", description="Supprimer une catégorie et toutes ses marques")
@app_commands.describe(nom="Nom exact de la catégorie à supprimer")
async def cat_delete(interaction: discord.Interaction, nom: str):
    await interaction.response.defer(ephemeral=True)
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, message_id, channel_id FROM categories WHERE LOWER(nom)=LOWER(?)", (nom,))
    row = c.fetchone()
    if not row:
        conn.close()
        await interaction.followup.send(embed=embed_err("Introuvable", f"Aucune catégorie **{nom}**."), ephemeral=True)
        return

    cat_id, message_id, channel_id = row

    # Supprimer le message Discord
    if message_id and channel_id:
        try:
            channel = bot.get_channel(int(channel_id))
            msg = await channel.fetch_message(int(message_id))
            await msg.delete()
        except:
            pass

    c.execute("DELETE FROM marques WHERE categorie_id=?", (cat_id,))
    c.execute("DELETE FROM categories WHERE id=?", (cat_id,))
    conn.commit()
    conn.close()
    await interaction.followup.send(embed=embed_ok("Catégorie supprimée", f"**{nom}** et ses marques ont été supprimées."))

@bot.tree.command(name="cat_rename", description="Renommer une catégorie")
@app_commands.describe(ancien_nom="Nom actuel", nouveau_nom="Nouveau nom")
async def cat_rename(interaction: discord.Interaction, ancien_nom: str, nouveau_nom: str):
    await interaction.response.defer(ephemeral=True)
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, statut FROM categories WHERE LOWER(nom)=LOWER(?)", (ancien_nom,))
    row = c.fetchone()
    if not row:
        conn.close()
        await interaction.followup.send(embed=embed_err("Introuvable", f"Aucune catégorie **{ancien_nom}**."), ephemeral=True)
        return
    cat_id, statut = row
    c.execute("UPDATE categories SET nom=? WHERE id=?", (nouveau_nom, cat_id))
    conn.commit()
    conn.close()
    await refresh_categorie(cat_id)
    await interaction.followup.send(embed=embed_ok("Catégorie renommée", f"**{ancien_nom}** → **{nouveau_nom}**"))

@bot.tree.command(name="cat_list", description="Lister toutes les catégories")
async def cat_list(interaction: discord.Interaction):
    conn = get_db()
    c = conn.cursor()
    c.execute("""SELECT cat.nom, cat.statut, COUNT(m.id)
                 FROM categories cat
                 LEFT JOIN marques m ON m.categorie_id = cat.id
                 GROUP BY cat.id ORDER BY cat.statut, cat.position""")
    rows = c.fetchall()
    conn.close()
    if not rows:
        await interaction.response.send_message(embed=embed_err("Aucune catégorie", "Crée une catégorie avec `/cat_add`."), ephemeral=True)
        return

    icones = {"eligible": "🟢", "facture_10": "🟡", "facture_100": "🟠", "bloquee": "🔴"}
    e = discord.Embed(title="Liste des catégories", color=0x3498db)
    by_statut = {}
    for r in rows:
        by_statut.setdefault(r[1], []).append(r)
    for statut, items in by_statut.items():
        val = "\n".join([f"{icones.get(statut,'⚪')} **{r[0]}** — {r[2]} marque(s)" for r in items])
        e.add_field(name=TITRES_CHANNEL.get(statut, statut), value=val, inline=False)
    await interaction.response.send_message(embed=e, ephemeral=True)

# ══════════════════════════════════════════════════════════════
#  MARQUES
# ══════════════════════════════════════════════════════════════

@bot.tree.command(name="marque_add", description="Ajouter une marque dans une catégorie")
@app_commands.describe(
    categorie="Nom exact de la catégorie",
    nom="Nom de la marque"
)
async def marque_add(interaction: discord.Interaction, categorie: str, nom: str):
    await interaction.response.defer(ephemeral=True)
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id FROM categories WHERE LOWER(nom)=LOWER(?)", (categorie,))
    cat = c.fetchone()
    if not cat:
        conn.close()
        await interaction.followup.send(embed=embed_err("Catégorie introuvable", f"**{categorie}** n'existe pas. Crée-la avec `/cat_add`."), ephemeral=True)
        return
    cat_id = cat[0]

    c.execute("SELECT id FROM marques WHERE LOWER(nom)=LOWER(?) AND categorie_id=?", (nom, cat_id))
    if c.fetchone():
        conn.close()
        await interaction.followup.send(embed=embed_err("Déjà existante", f"**{nom}** est déjà dans **{categorie}**."), ephemeral=True)
        return

    c.execute("SELECT MAX(position) FROM marques WHERE categorie_id=?", (cat_id,))
    max_pos = c.fetchone()[0] or 0
    c.execute("INSERT INTO marques (nom, categorie_id, position, date_ajout) VALUES (?,?,?,?)",
              (nom, cat_id, max_pos + 1, datetime.now().strftime("%d/%m/%Y")))
    conn.commit()
    conn.close()

    await refresh_categorie(cat_id)
    await interaction.followup.send(embed=embed_ok("Marque ajoutée", f"**{nom}** ajoutée dans **{categorie.upper()}**"))

@bot.tree.command(name="marque_delete", description="Supprimer une marque")
@app_commands.describe(categorie="Nom de la catégorie", nom="Nom de la marque à supprimer")
async def marque_delete(interaction: discord.Interaction, categorie: str, nom: str):
    await interaction.response.defer(ephemeral=True)
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id FROM categories WHERE LOWER(nom)=LOWER(?)", (categorie,))
    cat = c.fetchone()
    if not cat:
        conn.close()
        await interaction.followup.send(embed=embed_err("Catégorie introuvable", f"**{categorie}** n'existe pas."), ephemeral=True)
        return
    cat_id = cat[0]
    c.execute("DELETE FROM marques WHERE LOWER(nom)=LOWER(?) AND categorie_id=?", (nom, cat_id))
    if c.rowcount == 0:
        conn.close()
        await interaction.followup.send(embed=embed_err("Introuvable", f"**{nom}** n'est pas dans **{categorie}**."), ephemeral=True)
        return
    conn.commit()
    conn.close()
    await refresh_categorie(cat_id)
    await interaction.followup.send(embed=embed_ok("Marque supprimée", f"**{nom}** retirée de **{categorie.upper()}**"))

@bot.tree.command(name="marque_move", description="Déplacer une marque vers une autre catégorie")
@app_commands.describe(nom="Nom de la marque", cat_source="Catégorie actuelle", cat_destination="Nouvelle catégorie")
async def marque_move(interaction: discord.Interaction, nom: str, cat_source: str, cat_destination: str):
    await interaction.response.defer(ephemeral=True)
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id FROM categories WHERE LOWER(nom)=LOWER(?)", (cat_source,))
    src = c.fetchone()
    c.execute("SELECT id FROM categories WHERE LOWER(nom)=LOWER(?)", (cat_destination,))
    dst = c.fetchone()
    if not src or not dst:
        conn.close()
        await interaction.followup.send(embed=embed_err("Catégorie introuvable", "Vérifie les noms des catégories."), ephemeral=True)
        return
    src_id, dst_id = src[0], dst[0]
    c.execute("SELECT id FROM marques WHERE LOWER(nom)=LOWER(?) AND categorie_id=?", (nom, src_id))
    marque = c.fetchone()
    if not marque:
        conn.close()
        await interaction.followup.send(embed=embed_err("Introuvable", f"**{nom}** n'est pas dans **{cat_source}**."), ephemeral=True)
        return
    c.execute("SELECT MAX(position) FROM marques WHERE categorie_id=?", (dst_id,))
    max_pos = c.fetchone()[0] or 0
    c.execute("UPDATE marques SET categorie_id=?, position=? WHERE id=?", (dst_id, max_pos + 1, marque[0]))
    conn.commit()
    conn.close()
    await refresh_categorie(src_id)
    await refresh_categorie(dst_id)
    await interaction.followup.send(embed=embed_ok("Marque déplacée", f"**{nom}** → **{cat_destination.upper()}**"))

@bot.tree.command(name="marque_rename", description="Renommer une marque")
@app_commands.describe(categorie="Catégorie de la marque", ancien_nom="Nom actuel", nouveau_nom="Nouveau nom")
async def marque_rename(interaction: discord.Interaction, categorie: str, ancien_nom: str, nouveau_nom: str):
    await interaction.response.defer(ephemeral=True)
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id FROM categories WHERE LOWER(nom)=LOWER(?)", (categorie,))
    cat = c.fetchone()
    if not cat:
        conn.close()
        await interaction.followup.send(embed=embed_err("Catégorie introuvable", f"**{categorie}** n'existe pas."), ephemeral=True)
        return
    cat_id = cat[0]
    c.execute("UPDATE marques SET nom=? WHERE LOWER(nom)=LOWER(?) AND categorie_id=?", (nouveau_nom, ancien_nom, cat_id))
    if c.rowcount == 0:
        conn.close()
        await interaction.followup.send(embed=embed_err("Introuvable", f"**{ancien_nom}** n'est pas dans **{categorie}**."), ephemeral=True)
        return
    conn.commit()
    conn.close()
    await refresh_categorie(cat_id)
    await interaction.followup.send(embed=embed_ok("Marque renommée", f"**{ancien_nom}** → **{nouveau_nom}**"))

@bot.tree.command(name="refresh", description="Rafraîchir manuellement tous les messages de ce channel")
async def refresh(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id FROM categories WHERE channel_id=?", (str(interaction.channel.id),))
    cats = c.fetchall()
    conn.close()
    for (cat_id,) in cats:
        await refresh_categorie(cat_id)
    await interaction.followup.send(embed=embed_ok("Rafraîchi", f"{len(cats)} catégorie(s) mises à jour."), ephemeral=True)

# ══════════════════════════════════════════════════════════════
#  MAGASINS
# ══════════════════════════════════════════════════════════════

@bot.tree.command(name="magasin_add", description="Ajouter un magasin physique")
@app_commands.describe(nom="Nom du magasin", ville="Ville", adresse="Adresse", notes="Notes")
async def magasin_add(interaction: discord.Interaction, nom: str, ville: str = "", adresse: str = "", notes: str = ""):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO magasins (nom, ville, adresse, notes, date_ajout) VALUES (?,?,?,?,?)",
              (nom, ville, adresse, notes, datetime.now().strftime("%d/%m/%Y")))
    conn.commit()
    conn.close()
    e = embed_ok("Magasin ajouté", f"🏪 **{nom}**")
    if ville: e.add_field(name="Ville", value=ville, inline=True)
    if adresse: e.add_field(name="Adresse", value=adresse, inline=True)
    if notes: e.add_field(name="Notes", value=notes, inline=False)
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="magasin_delete", description="Supprimer un magasin")
@app_commands.describe(nom="Nom du magasin")
async def magasin_delete(interaction: discord.Interaction, nom: str):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM magasins WHERE LOWER(nom)=LOWER(?)", (nom,))
    if c.rowcount == 0:
        conn.close()
        await interaction.response.send_message(embed=embed_err("Introuvable", f"**{nom}** introuvable."), ephemeral=True)
        return
    conn.commit()
    conn.close()
    await interaction.response.send_message(embed=embed_ok("Magasin supprimé", f"**{nom}** supprimé."))

@bot.tree.command(name="magasin_list", description="Lister tous les magasins")
async def magasin_list(interaction: discord.Interaction):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT nom, ville, adresse, notes FROM magasins ORDER BY ville, nom")
    rows = c.fetchall()
    conn.close()
    if not rows:
        await interaction.response.send_message(embed=embed_err("Aucun magasin", "Ajoute-en un avec `/magasin_add`."), ephemeral=True)
        return
    e = discord.Embed(title="🏪 Magasins physiques", color=0xe67e22)
    desc = ""
    for r in rows:
        desc += f"**{r[0]}**" + (f" — {r[1]}" if r[1] else "")
        if r[2]: desc += f"\n📍 {r[2]}"
        if r[3]: desc += f"\n*{r[3]}*"
        desc += "\n\n"
    e.description = desc[:4096]
    await interaction.response.send_message(embed=e)

# ══════════════════════════════════════════════════════════════
#  SITES / GROSSISTES
# ══════════════════════════════════════════════════════════════

@bot.tree.command(name="site_add", description="Ajouter un site ou grossiste (lien cliquable)")
@app_commands.describe(nom="Nom du site", url="URL complète", type_site="Type", notes="Notes")
@app_commands.choices(type_site=[
    app_commands.Choice(name="Grossiste", value="grossiste"),
    app_commands.Choice(name="Retailer", value="retailer"),
    app_commands.Choice(name="Marketplace", value="marketplace"),
    app_commands.Choice(name="Autre", value="autre"),
])
async def site_add(interaction: discord.Interaction, nom: str, url: str, type_site: str = "grossiste", notes: str = ""):
    if not url.startswith("http"): url = "https://" + url
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO sites (nom, url, type, notes, date_ajout) VALUES (?,?,?,?,?)",
              (nom, url, type_site, notes, datetime.now().strftime("%d/%m/%Y")))
    conn.commit()
    conn.close()
    e = embed_ok("Site ajouté", f"**[{nom}]({url})**")
    e.add_field(name="Type", value=type_site.capitalize(), inline=True)
    if notes: e.add_field(name="Notes", value=notes, inline=False)
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="site_delete", description="Supprimer un site")
@app_commands.describe(nom="Nom du site")
async def site_delete(interaction: discord.Interaction, nom: str):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM sites WHERE LOWER(nom)=LOWER(?)", (nom,))
    if c.rowcount == 0:
        conn.close()
        await interaction.response.send_message(embed=embed_err("Introuvable", f"**{nom}** introuvable."), ephemeral=True)
        return
    conn.commit()
    conn.close()
    await interaction.response.send_message(embed=embed_ok("Site supprimé", f"**{nom}** supprimé."))

@bot.tree.command(name="site_list", description="Lister tous les sites (liens cliquables)")
async def site_list(interaction: discord.Interaction):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT nom, url, type, notes FROM sites ORDER BY type, nom")
    rows = c.fetchall()
    conn.close()
    if not rows:
        await interaction.response.send_message(embed=embed_err("Aucun site", "Ajoute-en un avec `/site_add`."), ephemeral=True)
        return
    e = discord.Embed(title="🌐 Sites & Grossistes", description="Clique sur le nom pour ouvrir le site", color=0x1abc9c)
    by_type = {}
    for r in rows:
        by_type.setdefault(r[2], []).append(r)
    for t, items in by_type.items():
        val = "\n".join([f"**[{r[0]}]({r[1]})**" + (f"\n*{r[3]}*" if r[3] else "") for r in items])
        e.add_field(name=t.capitalize() + f"s ({len(items)})", value=val[:1024], inline=False)
    await interaction.response.send_message(embed=e)

# ══════════════════════════════════════════════════════════════
#  PRODUITS
# ══════════════════════════════════════════════════════════════

@bot.tree.command(name="produit_add", description="Ajouter un produit sourcé")
@app_commands.describe(nom="Nom", marque="Marque", asin="ASIN Amazon",
    prix_achat="Prix achat (€)", prix_vente="Prix vente Amazon (€)", fournisseur="Fournisseur", notes="Notes")
async def produit_add(interaction: discord.Interaction, nom: str, marque: str = "",
                      asin: str = "", prix_achat: float = 0.0, prix_vente: float = 0.0,
                      fournisseur: str = "", notes: str = ""):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO produits (nom, marque, asin, prix_achat, prix_vente, fournisseur, notes, date_ajout) VALUES (?,?,?,?,?,?,?,?)",
              (nom, marque, asin, prix_achat, prix_vente, fournisseur, notes, datetime.now().strftime("%d/%m/%Y")))
    conn.commit()
    conn.close()
    marge = round(prix_vente - prix_achat, 2) if prix_achat and prix_vente else None
    pct = round((marge / prix_achat) * 100, 1) if marge and prix_achat else None
    e = embed_ok("Produit ajouté", f"📦 **{nom}**")
    if marque: e.add_field(name="Marque", value=marque, inline=True)
    if asin: e.add_field(name="ASIN", value=f"[{asin}](https://www.amazon.fr/dp/{asin})", inline=True)
    if prix_achat: e.add_field(name="Achat", value=f"{prix_achat}€", inline=True)
    if prix_vente: e.add_field(name="Vente", value=f"{prix_vente}€", inline=True)
    if marge: e.add_field(name="Marge brute", value=f"**{marge}€ ({pct}%)**", inline=True)
    if fournisseur: e.add_field(name="Fournisseur", value=fournisseur, inline=True)
    if notes: e.add_field(name="Notes", value=notes, inline=False)
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="produit_delete", description="Supprimer un produit")
@app_commands.describe(nom="Nom du produit")
async def produit_delete(interaction: discord.Interaction, nom: str):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM produits WHERE LOWER(nom)=LOWER(?)", (nom,))
    if c.rowcount == 0:
        conn.close()
        await interaction.response.send_message(embed=embed_err("Introuvable", f"**{nom}** introuvable."), ephemeral=True)
        return
    conn.commit()
    conn.close()
    await interaction.response.send_message(embed=embed_ok("Produit supprimé", f"**{nom}** supprimé."))

@bot.tree.command(name="produit_list", description="Lister les produits sourcés")
@app_commands.choices(statut=[
    app_commands.Choice(name="Tous", value="tous"),
    app_commands.Choice(name="À tester", value="a_tester"),
    app_commands.Choice(name="Actifs", value="actif"),
    app_commands.Choice(name="Archivés", value="archive"),
])
async def produit_list(interaction: discord.Interaction, statut: str = "tous"):
    conn = get_db()
    c = conn.cursor()
    if statut == "tous":
        c.execute("SELECT nom, marque, asin, prix_achat, prix_vente, fournisseur, statut FROM produits ORDER BY statut, nom")
    else:
        c.execute("SELECT nom, marque, asin, prix_achat, prix_vente, fournisseur, statut FROM produits WHERE statut=? ORDER BY nom", (statut,))
    rows = c.fetchall()
    conn.close()
    if not rows:
        await interaction.response.send_message(embed=embed_err("Aucun produit", "Ajoute-en un avec `/produit_add`."), ephemeral=True)
        return
    e = discord.Embed(title="📦 Produits Sourcés", color=0xf39c12)
    icones = {"a_tester": "🔍", "actif": "✅", "archive": "📁"}
    for r in rows[:15]:
        nom, marque, asin, pa, pv, fourn, stat = r
        marge = round(pv - pa, 2) if pa and pv else None
        pct = round((marge / pa) * 100, 1) if marge and pa else None
        titre = f"{icones.get(stat,'📦')} **{nom}**" + (f" — {marque}" if marque else "")
        val = ""
        if asin: val += f"[Amazon 🔗](https://www.amazon.fr/dp/{asin})  "
        if pa: val += f"Achat: **{pa}€**  "
        if pv: val += f"Vente: **{pv}€**  "
        if marge: val += f"Marge: **{marge}€ ({pct}%)**"
        if fourn: val += f"\n{fourn}"
        e.add_field(name=titre, value=val or "*Pas de détails*", inline=False)
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="produit_statut", description="Changer le statut d'un produit")
@app_commands.choices(statut=[
    app_commands.Choice(name="À tester", value="a_tester"),
    app_commands.Choice(name="Actif", value="actif"),
    app_commands.Choice(name="Archivé", value="archive"),
])
async def produit_statut(interaction: discord.Interaction, nom: str, statut: str):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE produits SET statut=? WHERE LOWER(nom)=LOWER(?)", (statut, nom))
    if c.rowcount == 0:
        conn.close()
        await interaction.response.send_message(embed=embed_err("Introuvable", f"**{nom}** introuvable."), ephemeral=True)
        return
    conn.commit()
    conn.close()
    await interaction.response.send_message(embed=embed_ok("Statut mis à jour", f"**{nom}** → {statut}"))

# ══════════════════════════════════════════════════════════════
#  NOTES
# ══════════════════════════════════════════════════════════════

@bot.tree.command(name="note_add", description="Ajouter une note / mémo")
@app_commands.describe(titre="Titre", contenu="Contenu", categorie="Catégorie")
async def note_add(interaction: discord.Interaction, titre: str, contenu: str, categorie: str = "general"):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO notes (titre, contenu, categorie, date_ajout) VALUES (?,?,?,?)",
              (titre, contenu, categorie, datetime.now().strftime("%d/%m/%Y %H:%M")))
    conn.commit()
    conn.close()
    e = embed_ok("Note ajoutée", f"📝 **{titre}**")
    e.add_field(name="Catégorie", value=categorie, inline=True)
    e.add_field(name="Contenu", value=contenu[:1000], inline=False)
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="note_delete", description="Supprimer une note")
@app_commands.describe(titre="Titre de la note")
async def note_delete(interaction: discord.Interaction, titre: str):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM notes WHERE LOWER(titre)=LOWER(?)", (titre,))
    if c.rowcount == 0:
        conn.close()
        await interaction.response.send_message(embed=embed_err("Introuvable", f"**{titre}** introuvable."), ephemeral=True)
        return
    conn.commit()
    conn.close()
    await interaction.response.send_message(embed=embed_ok("Note supprimée", f"**{titre}** supprimée."))

@bot.tree.command(name="note_list", description="Lister toutes les notes")
async def note_list(interaction: discord.Interaction, categorie: str = ""):
    conn = get_db()
    c = conn.cursor()
    if categorie:
        c.execute("SELECT titre, contenu, categorie, date_ajout FROM notes WHERE LOWER(categorie)=LOWER(?) ORDER BY date_ajout DESC", (categorie,))
    else:
        c.execute("SELECT titre, contenu, categorie, date_ajout FROM notes ORDER BY date_ajout DESC")
    rows = c.fetchall()
    conn.close()
    if not rows:
        await interaction.response.send_message(embed=embed_err("Aucune note", "Ajoute-en une avec `/note_add`."), ephemeral=True)
        return
    e = discord.Embed(title="📝 Notes & Mémos", color=0x8e44ad)
    for r in rows[:10]:
        contenu = r[1][:200] + "..." if len(r[1]) > 200 else r[1]
        e.add_field(name=f"📝 {r[0]}  [{r[2]}]", value=f"{contenu}\n*{r[3]}*", inline=False)
    await interaction.response.send_message(embed=e)

# ══════════════════════════════════════════════════════════════
#  DASHBOARD & SEARCH
# ══════════════════════════════════════════════════════════════

@bot.tree.command(name="dashboard", description="Vue d'ensemble de ta base")
async def dashboard(interaction: discord.Interaction):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT statut, COUNT(*) FROM categories GROUP BY statut")
    cats = dict(c.fetchall())
    c.execute("SELECT COUNT(*) FROM marques")
    nb_marques = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM magasins")
    nb_mag = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM sites")
    nb_sites = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM produits WHERE statut='actif'")
    p_actif = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM produits WHERE statut='a_tester'")
    p_test = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM notes")
    nb_notes = c.fetchone()[0]
    c.execute("SELECT AVG(prix_vente-prix_achat) FROM produits WHERE prix_achat>0 AND prix_vente>0 AND statut='actif'")
    moy_marge = c.fetchone()[0]
    conn.close()

    e = discord.Embed(title="📊  Dashboard Business Amazon", color=0x2c3e50, timestamp=datetime.now())
    e.add_field(name="📋 Catégories & Marques", value=(
        f"🟢 Éligibles : {cats.get('eligible', 0)} cat.\n"
        f"🟡 Facture 10 : {cats.get('facture_10', 0)} cat.\n"
        f"🟠 Facture 100 : {cats.get('facture_100', 0)} cat.\n"
        f"🔴 Bloquées : {cats.get('bloquee', 0)} cat.\n"
        f"**{nb_marques} marques au total**"
    ), inline=True)
    e.add_field(name="📦 Produits", value=f"✅ {p_actif} actifs\n🔍 {p_test} à tester", inline=True)
    e.add_field(name="🌐 Sources", value=f"🏪 {nb_mag} magasins\n🌐 {nb_sites} sites", inline=True)
    if moy_marge:
        e.add_field(name="💰 Marge moy.", value=f"**{round(moy_marge,2)}€**", inline=True)
    e.add_field(name="📝 Notes", value=f"{nb_notes} mémos", inline=True)
    e.set_footer(text="Amazon Business Tracker")
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="search", description="Rechercher dans toute la base")
@app_commands.describe(query="Mot-clé")
async def search(interaction: discord.Interaction, query: str):
    conn = get_db()
    c = conn.cursor()
    q = f"%{query}%"
    c.execute("""SELECT m.nom, cat.nom, cat.statut FROM marques m
                 JOIN categories cat ON cat.id = m.categorie_id
                 WHERE m.nom LIKE ?""", (q,))
    marques = c.fetchall()
    c.execute("SELECT nom, ville FROM magasins WHERE nom LIKE ? OR ville LIKE ?", (q, q))
    magasins = c.fetchall()
    c.execute("SELECT nom, url FROM sites WHERE nom LIKE ?", (q,))
    sites = c.fetchall()
    c.execute("SELECT nom, marque FROM produits WHERE nom LIKE ? OR marque LIKE ?", (q, q))
    produits = c.fetchall()
    conn.close()

    total = len(marques) + len(magasins) + len(sites) + len(produits)
    if total == 0:
        await interaction.response.send_message(embed=embed_err("Aucun résultat", f"Rien trouvé pour **{query}**"), ephemeral=True)
        return

    icones_s = {"eligible": "🟢", "facture_10": "🟡", "facture_100": "🟠", "bloquee": "🔴"}
    e = discord.Embed(title=f"🔍  Résultats pour « {query} »", description=f"**{total} résultat(s)**", color=0x2980b9)
    if marques:
        e.add_field(name="Marques", value="\n".join([f"{icones_s.get(r[2],'⚪')} **{r[0]}** — *{r[1]}*" for r in marques]), inline=False)
    if magasins:
        e.add_field(name="Magasins", value="\n".join([f"🏪 **{r[0]}**" + (f" — {r[1]}" if r[1] else "") for r in magasins]), inline=False)
    if sites:
        e.add_field(name="Sites", value="\n".join([f"**[{r[0]}]({r[1]})**" for r in sites]), inline=False)
    if produits:
        e.add_field(name="Produits", value="\n".join([f"📦 **{r[0]}**" + (f" — {r[1]}" if r[1] else "") for r in produits]), inline=False)
    await interaction.response.send_message(embed=e)

# ══════════════════════════════════════════════════════════════
#  AIDE
# ══════════════════════════════════════════════════════════════

@bot.tree.command(name="aide", description="Toutes les commandes disponibles")
async def aide(interaction: discord.Interaction):
    e = discord.Embed(title="📖  Commandes du Bot", color=0x3498db)
    e.add_field(name="📂 CATÉGORIES", value=(
        "`/cat_add` — Créer une catégorie dans ce channel\n"
        "`/cat_delete` — Supprimer une catégorie\n"
        "`/cat_rename` — Renommer une catégorie\n"
        "`/cat_list` — Voir toutes les catégories"
    ), inline=False)
    e.add_field(name="🏷️ MARQUES", value=(
        "`/marque_add` — Ajouter dans une catégorie\n"
        "`/marque_delete` — Supprimer\n"
        "`/marque_rename` — Renommer\n"
        "`/marque_move` — Déplacer vers une autre catégorie"
    ), inline=False)
    e.add_field(name="🏪 MAGASINS", value=(
        "`/magasin_add` — Ajouter\n"
        "`/magasin_list` — Lister\n"
        "`/magasin_delete` — Supprimer"
    ), inline=False)
    e.add_field(name="🌐 SITES & GROSSISTES", value=(
        "`/site_add` — Ajouter (lien cliquable)\n"
        "`/site_list` — Lister\n"
        "`/site_delete` — Supprimer"
    ), inline=False)
    e.add_field(name="📦 PRODUITS", value=(
        "`/produit_add` — Ajouter avec calcul de marge\n"
        "`/produit_list` — Lister\n"
        "`/produit_statut` — Changer statut\n"
        "`/produit_delete` — Supprimer"
    ), inline=False)
    e.add_field(name="📝 NOTES", value=(
        "`/note_add` — Ajouter\n"
        "`/note_list` — Lister\n"
        "`/note_delete` — Supprimer"
    ), inline=False)
    e.add_field(name="🔧 OUTILS", value=(
        "`/dashboard` — Statistiques globales\n"
        "`/search` — Recherche globale\n"
        "`/refresh` — Rafraîchir les messages du channel\n"
        "`/aide` — Cette aide"
    ), inline=False)
    e.set_footer(text="Amazon Business Tracker 📦")
    await interaction.response.send_message(embed=e, ephemeral=True)

# ─────────────────────────────────────────
#  RUN
# ─────────────────────────────────────────
if __name__ == "__main__":
    bot.run(TOKEN)
