import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
import os
from datetime import datetime

# ─────────────────────────────────────────
#  CONFIG — remplace par ton token
# ─────────────────────────────────────────
TOKEN = os.getenv("DISCORD_TOKEN", "")
DB_PATH = "business.db"

# ─────────────────────────────────────────
#  DATABASE
# ─────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS marques (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT NOT NULL,
        statut TEXT NOT NULL DEFAULT 'eligible',  -- eligible | non_eligible
        categorie TEXT,
        notes TEXT,
        date_ajout TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS magasins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT NOT NULL,
        ville TEXT,
        adresse TEXT,
        notes TEXT,
        date_ajout TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS sites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT NOT NULL,
        url TEXT NOT NULL,
        type TEXT DEFAULT 'grossiste',  -- grossiste | retailer | marketplace | autre
        notes TEXT,
        date_ajout TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS produits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT NOT NULL,
        marque TEXT,
        asin TEXT,
        prix_achat REAL,
        prix_vente REAL,
        fournisseur TEXT,
        statut TEXT DEFAULT 'a_tester',  -- a_tester | actif | archive
        notes TEXT,
        date_ajout TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        titre TEXT NOT NULL,
        contenu TEXT NOT NULL,
        categorie TEXT DEFAULT 'general',
        date_ajout TEXT
    )""")

    conn.commit()
    conn.close()

def get_db():
    return sqlite3.connect(DB_PATH)

# ─────────────────────────────────────────
#  BOT SETUP
# ─────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ─────────────────────────────────────────
#  EMBEDS HELPERS
# ─────────────────────────────────────────
def embed_success(titre, description=""):
    e = discord.Embed(title=f"✅ {titre}", description=description, color=0x2ecc71)
    e.timestamp = datetime.now()
    return e

def embed_error(titre, description=""):
    e = discord.Embed(title=f"❌ {titre}", description=description, color=0xe74c3c)
    return e

def embed_info(titre, description="", color=0x3498db):
    e = discord.Embed(title=titre, description=description, color=color)
    e.timestamp = datetime.now()
    return e

# ─────────────────────────────────────────
#  EVENTS
# ─────────────────────────────────────────
@bot.event
async def on_ready():
    init_db()
    print(f"✅ Bot connecté : {bot.user} ({bot.user.id})")
    try:
        synced = await bot.tree.sync()
        print(f"✅ {len(synced)} commandes slash synchronisées")
    except Exception as e:
        print(f"❌ Erreur sync : {e}")
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.watching,
        name="ton business Amazon 📦"
    ))

# ══════════════════════════════════════════════════════════════
#  ██████  MARQUES
# ══════════════════════════════════════════════════════════════

@bot.tree.command(name="marque_add", description="Ajouter une marque éligible ou non éligible")
@app_commands.describe(
    nom="Nom de la marque",
    statut="eligible ou non_eligible",
    categorie="Catégorie produit (ex: électronique, jouets...)",
    notes="Notes supplémentaires"
)
@app_commands.choices(statut=[
    app_commands.Choice(name="✅ Éligible", value="eligible"),
    app_commands.Choice(name="❌ Non éligible", value="non_eligible"),
])
async def marque_add(interaction: discord.Interaction, nom: str, statut: str = "eligible",
                     categorie: str = "", notes: str = ""):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id FROM marques WHERE LOWER(nom) = LOWER(?)", (nom,))
    if c.fetchone():
        conn.close()
        await interaction.response.send_message(embed=embed_error("Marque déjà existante", f"**{nom}** est déjà dans la base."), ephemeral=True)
        return
    c.execute("INSERT INTO marques (nom, statut, categorie, notes, date_ajout) VALUES (?,?,?,?,?)",
              (nom, statut, categorie, notes, datetime.now().strftime("%d/%m/%Y")))
    conn.commit()
    conn.close()
    icone = "✅" if statut == "eligible" else "❌"
    e = embed_success("Marque ajoutée", f"{icone} **{nom}**")
    if categorie: e.add_field(name="Catégorie", value=categorie, inline=True)
    if notes: e.add_field(name="Notes", value=notes, inline=False)
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="marque_delete", description="Supprimer une marque")
@app_commands.describe(nom="Nom exact de la marque à supprimer")
async def marque_delete(interaction: discord.Interaction, nom: str):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM marques WHERE LOWER(nom) = LOWER(?)", (nom,))
    if c.rowcount == 0:
        conn.close()
        await interaction.response.send_message(embed=embed_error("Introuvable", f"Aucune marque **{nom}** trouvée."), ephemeral=True)
        return
    conn.commit()
    conn.close()
    await interaction.response.send_message(embed=embed_success("Marque supprimée", f"**{nom}** a été supprimée."))

@bot.tree.command(name="marque_list", description="Lister toutes les marques")
@app_commands.describe(filtre="Filtrer : toutes, eligible, non_eligible")
@app_commands.choices(filtre=[
    app_commands.Choice(name="Toutes", value="toutes"),
    app_commands.Choice(name="✅ Éligibles seulement", value="eligible"),
    app_commands.Choice(name="❌ Non éligibles seulement", value="non_eligible"),
])
async def marque_list(interaction: discord.Interaction, filtre: str = "toutes"):
    conn = get_db()
    c = conn.cursor()
    if filtre == "toutes":
        c.execute("SELECT nom, statut, categorie, notes FROM marques ORDER BY statut, nom")
    else:
        c.execute("SELECT nom, statut, categorie, notes FROM marques WHERE statut=? ORDER BY nom", (filtre,))
    rows = c.fetchall()
    conn.close()

    if not rows:
        await interaction.response.send_message(embed=embed_info("📋 Marques", "Aucune marque enregistrée."), ephemeral=True)
        return

    eligibles = [r for r in rows if r[1] == "eligible"]
    non_eligibles = [r for r in rows if r[1] == "non_eligible"]

    e = embed_info("📋 Liste des Marques", f"**{len(rows)} marque(s)** au total", color=0x9b59b6)

    if eligibles and filtre in ("toutes", "eligible"):
        val = "\n".join([f"✅ **{r[0]}**" + (f" — *{r[2]}*" if r[2] else "") + (f"\n   ↳ {r[3]}" if r[3] else "") for r in eligibles])
        # Discord field max 1024 chars
        if len(val) > 1024: val = val[:1020] + "..."
        e.add_field(name=f"✅ Éligibles ({len(eligibles)})", value=val, inline=False)

    if non_eligibles and filtre in ("toutes", "non_eligible"):
        val = "\n".join([f"❌ **{r[0]}**" + (f" — *{r[2]}*" if r[2] else "") + (f"\n   ↳ {r[3]}" if r[3] else "") for r in non_eligibles])
        if len(val) > 1024: val = val[:1020] + "..."
        e.add_field(name=f"❌ Non éligibles ({len(non_eligibles)})", value=val, inline=False)

    await interaction.response.send_message(embed=e)

@bot.tree.command(name="marque_edit", description="Modifier le statut ou les notes d'une marque")
@app_commands.describe(nom="Nom de la marque", statut="Nouveau statut", notes="Nouvelles notes")
@app_commands.choices(statut=[
    app_commands.Choice(name="✅ Éligible", value="eligible"),
    app_commands.Choice(name="❌ Non éligible", value="non_eligible"),
])
async def marque_edit(interaction: discord.Interaction, nom: str, statut: str = None, notes: str = None):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, statut, notes FROM marques WHERE LOWER(nom) = LOWER(?)", (nom,))
    row = c.fetchone()
    if not row:
        conn.close()
        await interaction.response.send_message(embed=embed_error("Introuvable", f"Aucune marque **{nom}** trouvée."), ephemeral=True)
        return
    new_statut = statut or row[1]
    new_notes = notes if notes is not None else row[2]
    c.execute("UPDATE marques SET statut=?, notes=? WHERE id=?", (new_statut, new_notes, row[0]))
    conn.commit()
    conn.close()
    await interaction.response.send_message(embed=embed_success("Marque mise à jour", f"**{nom}** → {new_statut}"))

# ══════════════════════════════════════════════════════════════
#  🏪 MAGASINS
# ══════════════════════════════════════════════════════════════

@bot.tree.command(name="magasin_add", description="Ajouter un magasin physique")
@app_commands.describe(nom="Nom du magasin", ville="Ville", adresse="Adresse complète", notes="Notes")
async def magasin_add(interaction: discord.Interaction, nom: str, ville: str = "", adresse: str = "", notes: str = ""):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO magasins (nom, ville, adresse, notes, date_ajout) VALUES (?,?,?,?,?)",
              (nom, ville, adresse, notes, datetime.now().strftime("%d/%m/%Y")))
    conn.commit()
    conn.close()
    e = embed_success("Magasin ajouté", f"🏪 **{nom}**")
    if ville: e.add_field(name="Ville", value=ville, inline=True)
    if adresse: e.add_field(name="Adresse", value=adresse, inline=True)
    if notes: e.add_field(name="Notes", value=notes, inline=False)
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="magasin_delete", description="Supprimer un magasin")
@app_commands.describe(nom="Nom du magasin à supprimer")
async def magasin_delete(interaction: discord.Interaction, nom: str):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM magasins WHERE LOWER(nom) = LOWER(?)", (nom,))
    if c.rowcount == 0:
        conn.close()
        await interaction.response.send_message(embed=embed_error("Introuvable", f"Aucun magasin **{nom}** trouvé."), ephemeral=True)
        return
    conn.commit()
    conn.close()
    await interaction.response.send_message(embed=embed_success("Magasin supprimé", f"**{nom}** supprimé."))

@bot.tree.command(name="magasin_list", description="Lister tous les magasins")
async def magasin_list(interaction: discord.Interaction):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT nom, ville, adresse, notes, date_ajout FROM magasins ORDER BY ville, nom")
    rows = c.fetchall()
    conn.close()
    if not rows:
        await interaction.response.send_message(embed=embed_info("🏪 Magasins", "Aucun magasin enregistré."), ephemeral=True)
        return
    e = embed_info("🏪 Magasins physiques", f"**{len(rows)} magasin(s)**", color=0xe67e22)
    desc = ""
    for r in rows:
        desc += f"🏪 **{r[0]}**"
        if r[1]: desc += f" — {r[1]}"
        if r[2]: desc += f"\n   📍 {r[2]}"
        if r[3]: desc += f"\n   ↳ {r[3]}"
        desc += f"\n   *Ajouté le {r[4]}*\n\n"
    if len(desc) > 4096: desc = desc[:4090] + "..."
    e.description = desc
    await interaction.response.send_message(embed=e)

# ══════════════════════════════════════════════════════════════
#  🌐 SITES / GROSSISTES
# ══════════════════════════════════════════════════════════════

@bot.tree.command(name="site_add", description="Ajouter un site / grossiste en ligne")
@app_commands.describe(nom="Nom du site", url="URL complète (https://...)", type_site="Type de site", notes="Notes")
@app_commands.choices(type_site=[
    app_commands.Choice(name="🏭 Grossiste", value="grossiste"),
    app_commands.Choice(name="🛒 Retailer", value="retailer"),
    app_commands.Choice(name="🛍️ Marketplace", value="marketplace"),
    app_commands.Choice(name="📦 Autre", value="autre"),
])
async def site_add(interaction: discord.Interaction, nom: str, url: str, type_site: str = "grossiste", notes: str = ""):
    if not url.startswith("http"):
        url = "https://" + url
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO sites (nom, url, type, notes, date_ajout) VALUES (?,?,?,?,?)",
              (nom, url, type_site, notes, datetime.now().strftime("%d/%m/%Y")))
    conn.commit()
    conn.close()
    icones = {"grossiste": "🏭", "retailer": "🛒", "marketplace": "🛍️", "autre": "📦"}
    e = embed_success("Site ajouté", f"{icones.get(type_site,'🌐')} **[{nom}]({url})**")
    e.add_field(name="Type", value=type_site.capitalize(), inline=True)
    e.add_field(name="URL", value=url, inline=True)
    if notes: e.add_field(name="Notes", value=notes, inline=False)
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="site_delete", description="Supprimer un site")
@app_commands.describe(nom="Nom du site à supprimer")
async def site_delete(interaction: discord.Interaction, nom: str):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM sites WHERE LOWER(nom) = LOWER(?)", (nom,))
    if c.rowcount == 0:
        conn.close()
        await interaction.response.send_message(embed=embed_error("Introuvable", f"Aucun site **{nom}** trouvé."), ephemeral=True)
        return
    conn.commit()
    conn.close()
    await interaction.response.send_message(embed=embed_success("Site supprimé", f"**{nom}** supprimé."))

@bot.tree.command(name="site_list", description="Lister tous les sites/grossistes (avec liens cliquables)")
@app_commands.describe(filtre="Filtrer par type")
@app_commands.choices(filtre=[
    app_commands.Choice(name="Tous", value="tous"),
    app_commands.Choice(name="🏭 Grossistes", value="grossiste"),
    app_commands.Choice(name="🛒 Retailers", value="retailer"),
    app_commands.Choice(name="🛍️ Marketplaces", value="marketplace"),
])
async def site_list(interaction: discord.Interaction, filtre: str = "tous"):
    conn = get_db()
    c = conn.cursor()
    if filtre == "tous":
        c.execute("SELECT nom, url, type, notes, date_ajout FROM sites ORDER BY type, nom")
    else:
        c.execute("SELECT nom, url, type, notes, date_ajout FROM sites WHERE type=? ORDER BY nom", (filtre,))
    rows = c.fetchall()
    conn.close()
    if not rows:
        await interaction.response.send_message(embed=embed_info("🌐 Sites", "Aucun site enregistré."), ephemeral=True)
        return

    icones = {"grossiste": "🏭", "retailer": "🛒", "marketplace": "🛍️", "autre": "📦"}
    e = embed_info("🌐 Sites & Grossistes", f"**{len(rows)} site(s)** — clique sur le nom pour ouvrir", color=0x1abc9c)

    by_type = {}
    for r in rows:
        by_type.setdefault(r[2], []).append(r)

    for t, items in by_type.items():
        val = ""
        for r in items:
            val += f"{icones.get(t,'🌐')} **[{r[0]}]({r[1]})**"
            if r[3]: val += f"\n   ↳ {r[3]}"
            val += "\n"
        if len(val) > 1024: val = val[:1020] + "..."
        e.add_field(name=f"{icones.get(t,'📦')} {t.capitalize()}s ({len(items)})", value=val, inline=False)

    await interaction.response.send_message(embed=e)

# ══════════════════════════════════════════════════════════════
#  📦 PRODUITS SOURCÉS
# ══════════════════════════════════════════════════════════════

@bot.tree.command(name="produit_add", description="Ajouter un produit sourcé")
@app_commands.describe(
    nom="Nom du produit", marque="Marque", asin="ASIN Amazon",
    prix_achat="Prix d'achat (€)", prix_vente="Prix de vente Amazon (€)",
    fournisseur="Fournisseur / Source", notes="Notes"
)
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

    e = embed_success("Produit ajouté", f"📦 **{nom}**")
    if marque: e.add_field(name="Marque", value=marque, inline=True)
    if asin:
        e.add_field(name="ASIN", value=f"[{asin}](https://www.amazon.fr/dp/{asin})", inline=True)
    if prix_achat: e.add_field(name="Prix achat", value=f"{prix_achat}€", inline=True)
    if prix_vente: e.add_field(name="Prix vente", value=f"{prix_vente}€", inline=True)
    if marge is not None: e.add_field(name="Marge brute", value=f"**{marge}€** ({pct}%)", inline=True)
    if fournisseur: e.add_field(name="Fournisseur", value=fournisseur, inline=True)
    if notes: e.add_field(name="Notes", value=notes, inline=False)
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="produit_delete", description="Supprimer un produit")
@app_commands.describe(nom="Nom du produit à supprimer")
async def produit_delete(interaction: discord.Interaction, nom: str):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM produits WHERE LOWER(nom) = LOWER(?)", (nom,))
    if c.rowcount == 0:
        conn.close()
        await interaction.response.send_message(embed=embed_error("Introuvable", f"Aucun produit **{nom}** trouvé."), ephemeral=True)
        return
    conn.commit()
    conn.close()
    await interaction.response.send_message(embed=embed_success("Produit supprimé", f"**{nom}** supprimé."))

@bot.tree.command(name="produit_list", description="Lister les produits sourcés")
@app_commands.describe(statut="Filtrer par statut")
@app_commands.choices(statut=[
    app_commands.Choice(name="Tous", value="tous"),
    app_commands.Choice(name="🔍 À tester", value="a_tester"),
    app_commands.Choice(name="✅ Actifs", value="actif"),
    app_commands.Choice(name="📁 Archivés", value="archive"),
])
async def produit_list(interaction: discord.Interaction, statut: str = "tous"):
    conn = get_db()
    c = conn.cursor()
    if statut == "tous":
        c.execute("SELECT nom, marque, asin, prix_achat, prix_vente, fournisseur, statut, notes FROM produits ORDER BY statut, nom")
    else:
        c.execute("SELECT nom, marque, asin, prix_achat, prix_vente, fournisseur, statut, notes FROM produits WHERE statut=? ORDER BY nom", (statut,))
    rows = c.fetchall()
    conn.close()
    if not rows:
        await interaction.response.send_message(embed=embed_info("📦 Produits", "Aucun produit enregistré."), ephemeral=True)
        return

    e = embed_info("📦 Produits Sourcés", f"**{len(rows)} produit(s)**", color=0xf39c12)
    icones_s = {"a_tester": "🔍", "actif": "✅", "archive": "📁"}

    for r in rows:
        nom, marque, asin, pa, pv, fourn, stat, notes = r
        marge = round(pv - pa, 2) if pa and pv else None
        pct = round((marge / pa) * 100, 1) if marge and pa else None
        titre = f"{icones_s.get(stat,'📦')} **{nom}**" + (f" — {marque}" if marque else "")
        val = ""
        if asin: val += f"[Amazon 🔗](https://www.amazon.fr/dp/{asin})  "
        if pa: val += f"Achat: **{pa}€**  "
        if pv: val += f"Vente: **{pv}€**  "
        if marge: val += f"Marge: **{marge}€ ({pct}%)**"
        if fourn: val += f"\nFournisseur: {fourn}"
        if notes: val += f"\n*{notes}*"
        if not val: val = "*Pas de détails*"
        if len(val) > 1024: val = val[:1020] + "..."
        e.add_field(name=titre, value=val, inline=False)

    await interaction.response.send_message(embed=e)

@bot.tree.command(name="produit_statut", description="Changer le statut d'un produit")
@app_commands.describe(nom="Nom du produit")
@app_commands.choices(statut=[
    app_commands.Choice(name="🔍 À tester", value="a_tester"),
    app_commands.Choice(name="✅ Actif", value="actif"),
    app_commands.Choice(name="📁 Archivé", value="archive"),
])
async def produit_statut(interaction: discord.Interaction, nom: str, statut: str):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE produits SET statut=? WHERE LOWER(nom)=LOWER(?)", (statut, nom))
    if c.rowcount == 0:
        conn.close()
        await interaction.response.send_message(embed=embed_error("Introuvable", f"Aucun produit **{nom}** trouvé."), ephemeral=True)
        return
    conn.commit()
    conn.close()
    await interaction.response.send_message(embed=embed_success("Statut mis à jour", f"**{nom}** → {statut}"))

# ══════════════════════════════════════════════════════════════
#  📝 NOTES / MÉMOS
# ══════════════════════════════════════════════════════════════

@bot.tree.command(name="note_add", description="Ajouter une note / mémo")
@app_commands.describe(titre="Titre de la note", contenu="Contenu de la note", categorie="Catégorie")
async def note_add(interaction: discord.Interaction, titre: str, contenu: str, categorie: str = "general"):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO notes (titre, contenu, categorie, date_ajout) VALUES (?,?,?,?)",
              (titre, contenu, categorie, datetime.now().strftime("%d/%m/%Y %H:%M")))
    conn.commit()
    conn.close()
    e = embed_success("Note ajoutée", f"📝 **{titre}**")
    e.add_field(name="Catégorie", value=categorie, inline=True)
    e.add_field(name="Contenu", value=contenu[:1000], inline=False)
    await interaction.response.send_message(embed=e)

@bot.tree.command(name="note_delete", description="Supprimer une note par son titre")
@app_commands.describe(titre="Titre de la note à supprimer")
async def note_delete(interaction: discord.Interaction, titre: str):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM notes WHERE LOWER(titre) = LOWER(?)", (titre,))
    if c.rowcount == 0:
        conn.close()
        await interaction.response.send_message(embed=embed_error("Introuvable", f"Aucune note **{titre}** trouvée."), ephemeral=True)
        return
    conn.commit()
    conn.close()
    await interaction.response.send_message(embed=embed_success("Note supprimée", f"**{titre}** supprimée."))

@bot.tree.command(name="note_list", description="Lister toutes les notes")
@app_commands.describe(categorie="Filtrer par catégorie (laisser vide = toutes)")
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
        await interaction.response.send_message(embed=embed_info("📝 Notes", "Aucune note enregistrée."), ephemeral=True)
        return
    e = embed_info("📝 Notes & Mémos", f"**{len(rows)} note(s)**", color=0x8e44ad)
    for r in rows[:10]:  # max 10 pour éviter de dépasser Discord
        contenu = r[1][:200] + "..." if len(r[1]) > 200 else r[1]
        e.add_field(name=f"📝 {r[0]} *[{r[2]}]*", value=f"{contenu}\n*{r[3]}*", inline=False)
    if len(rows) > 10:
        e.set_footer(text=f"Affichage des 10 dernières notes sur {len(rows)}")
    await interaction.response.send_message(embed=e)

# ══════════════════════════════════════════════════════════════
#  📊 DASHBOARD / RÉSUMÉ
# ══════════════════════════════════════════════════════════════

@bot.tree.command(name="dashboard", description="Vue d'ensemble de ta base de données business")
async def dashboard(interaction: discord.Interaction):
    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM marques WHERE statut='eligible'")
    m_ok = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM marques WHERE statut='non_eligible'")
    m_nok = c.fetchone()[0]
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
    c.execute("SELECT AVG(prix_vente - prix_achat) FROM produits WHERE prix_achat > 0 AND prix_vente > 0 AND statut='actif'")
    moy_marge = c.fetchone()[0]
    conn.close()

    e = discord.Embed(title="📊 Dashboard Business Amazon", color=0x2c3e50, timestamp=datetime.now())
    e.add_field(name="📋 Marques", value=f"✅ {m_ok} éligibles\n❌ {m_nok} non éligibles", inline=True)
    e.add_field(name="🏪 Magasins", value=f"{nb_mag} magasins", inline=True)
    e.add_field(name="🌐 Sites", value=f"{nb_sites} sites/grossistes", inline=True)
    e.add_field(name="📦 Produits", value=f"✅ {p_actif} actifs\n🔍 {p_test} à tester", inline=True)
    e.add_field(name="📝 Notes", value=f"{nb_notes} mémos", inline=True)
    if moy_marge:
        e.add_field(name="💰 Marge moy. (actifs)", value=f"**{round(moy_marge, 2)}€**", inline=True)
    e.set_footer(text="Amazon Business Tracker")
    await interaction.response.send_message(embed=e)

# ══════════════════════════════════════════════════════════════
#  🔍 RECHERCHE GLOBALE
# ══════════════════════════════════════════════════════════════

@bot.tree.command(name="search", description="Rechercher dans toute la base de données")
@app_commands.describe(query="Mot-clé à rechercher")
async def search(interaction: discord.Interaction, query: str):
    conn = get_db()
    c = conn.cursor()
    q = f"%{query}%"

    c.execute("SELECT nom, statut FROM marques WHERE nom LIKE ?", (q,))
    marques = c.fetchall()
    c.execute("SELECT nom, ville FROM magasins WHERE nom LIKE ? OR ville LIKE ?", (q, q))
    magasins = c.fetchall()
    c.execute("SELECT nom, url FROM sites WHERE nom LIKE ?", (q,))
    sites = c.fetchall()
    c.execute("SELECT nom, marque, asin FROM produits WHERE nom LIKE ? OR marque LIKE ? OR asin LIKE ?", (q, q, q))
    produits = c.fetchall()
    c.execute("SELECT titre, categorie FROM notes WHERE titre LIKE ? OR contenu LIKE ?", (q, q))
    notes = c.fetchall()
    conn.close()

    total = len(marques) + len(magasins) + len(sites) + len(produits) + len(notes)
    if total == 0:
        await interaction.response.send_message(embed=embed_error("Aucun résultat", f"Rien trouvé pour **{query}**"), ephemeral=True)
        return

    e = embed_info(f"🔍 Résultats pour « {query} »", f"**{total} résultat(s)**", color=0x2980b9)
    if marques:
        e.add_field(name="📋 Marques", value="\n".join([f"{'✅' if r[1]=='eligible' else '❌'} {r[0]}" for r in marques]), inline=False)
    if magasins:
        e.add_field(name="🏪 Magasins", value="\n".join([f"🏪 {r[0]}" + (f" — {r[1]}" if r[1] else "") for r in magasins]), inline=False)
    if sites:
        e.add_field(name="🌐 Sites", value="\n".join([f"[{r[0]}]({r[1]})" for r in sites]), inline=False)
    if produits:
        e.add_field(name="📦 Produits", value="\n".join([f"📦 {r[0]}" + (f" — {r[1]}" if r[1] else "") for r in produits]), inline=False)
    if notes:
        e.add_field(name="📝 Notes", value="\n".join([f"📝 {r[0]} *[{r[1]}]*" for r in notes]), inline=False)

    await interaction.response.send_message(embed=e)

# ══════════════════════════════════════════════════════════════
#  ❓ AIDE
# ══════════════════════════════════════════════════════════════

@bot.tree.command(name="aide", description="Afficher toutes les commandes disponibles")
async def aide(interaction: discord.Interaction):
    e = discord.Embed(title="📖 Commandes du Bot Amazon Business", color=0x3498db)
    e.add_field(name="📋 MARQUES", value=(
        "`/marque_add` — Ajouter une marque\n"
        "`/marque_edit` — Modifier statut/notes\n"
        "`/marque_list` — Lister (toutes / éligibles / non)\n"
        "`/marque_delete` — Supprimer"
    ), inline=False)
    e.add_field(name="🏪 MAGASINS", value=(
        "`/magasin_add` — Ajouter un magasin\n"
        "`/magasin_list` — Lister\n"
        "`/magasin_delete` — Supprimer"
    ), inline=False)
    e.add_field(name="🌐 SITES & GROSSISTES", value=(
        "`/site_add` — Ajouter (lien cliquable auto)\n"
        "`/site_list` — Lister par type\n"
        "`/site_delete` — Supprimer"
    ), inline=False)
    e.add_field(name="📦 PRODUITS SOURCÉS", value=(
        "`/produit_add` — Ajouter avec prix & marge\n"
        "`/produit_list` — Lister / filtrer\n"
        "`/produit_statut` — Changer statut\n"
        "`/produit_delete` — Supprimer"
    ), inline=False)
    e.add_field(name="📝 NOTES", value=(
        "`/note_add` — Ajouter une note\n"
        "`/note_list` — Lister\n"
        "`/note_delete` — Supprimer"
    ), inline=False)
    e.add_field(name="🔧 OUTILS", value=(
        "`/dashboard` — Vue d'ensemble stats\n"
        "`/search` — Recherche globale\n"
        "`/aide` — Cette aide"
    ), inline=False)
    e.set_footer(text="Développé pour ton business Amazon 📦")
    await interaction.response.send_message(embed=e, ephemeral=True)

# ─────────────────────────────────────────
#  RUN
# ─────────────────────────────────────────
if __name__ == "__main__":
    bot.run(TOKEN)
