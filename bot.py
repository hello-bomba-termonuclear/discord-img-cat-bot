import os
import json
import time
import random
import logging
import asyncio

import aiohttp
from aiohttp import web
import discord
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()

# ───────────────────────── Config ─────────────────────────
TOKEN    = os.getenv("DISCORD_TOKEN")
PORT     = int(os.getenv("PORT", 8080))
COOLDOWN = 3.0  # segundos, cooldown global entre comandos

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("bot")

# ───────────────────────── Bancos de Imagens ─────────────────────────
# Carrega o JSON do comando /cat
with open("imagens.json", encoding="utf-8") as f:
    CAT_BANCO: list[str] = json.load(f)

# Carrega o JSON do comando /girl
with open("imagens_girl.json", encoding="utf-8") as f:
    GIRL_BANCO_RAW: list[str] = json.load(f)

# Remove duplicatas do banco de garotas para garantir sorteio uniforme
GIRL_BANCO: list[str] = list(set(GIRL_BANCO_RAW))

_ultimo_uso: float = 0.0

# ───────────────────────── Bot ─────────────────────────
intents = discord.Intents.default()
bot     = discord.Client(intents=intents)
tree    = app_commands.CommandTree(bot)


async def _executar_comando(interaction: discord.Interaction, banco: list[str], nome: str):
    """Lógica compartilhada de cooldown, sorteio e envio de embed."""
    global _ultimo_uso

    agora    = time.time()
    restante = COOLDOWN - (agora - _ultimo_uso)
    if restante > 0:
        await interaction.response.send_message(
            f"⏳ Calma! Tente novamente em {restante:.1f}s.",
            ephemeral=True,
        )
        return

    # Reserva o slot antes de qualquer await para evitar corrida
    _ultimo_uso = agora

    await interaction.response.defer()
    url = random.choice(banco)

    embed = discord.Embed(color=0xFFB6C1)
    embed.set_image(url=url)
    await interaction.followup.send(embed=embed)


# ───────────────────────── Comandos ─────────────────────────
@tree.command(name="cat", description="Envia um gatinho aleatório!")
async def cat(interaction: discord.Interaction):
    await _executar_comando(interaction, CAT_BANCO, "cat")


@tree.command(name="girl", description="Envia uma imagem aleatória da galeria!")
async def girl(interaction: discord.Interaction):
    await _executar_comando(interaction, GIRL_BANCO, "girl")


# ───────────────────────── Eventos ─────────────────────────
@bot.event
async def on_ready():
    await tree.sync()
    log.info("Bot conectado como %s (id=%s)", bot.user, bot.user.id)


# ───────────────────────── Servidor HTTP (health check) ─────────────────────────
async def _handle_ping(request: web.Request) -> web.Response:
    """Endpoint para o cronjob do Render manter o serviço acordado."""
    return web.Response(
        text=f"🐱 ok — bot online: {bot.is_ready()}",
        status=200,
        content_type="text/plain",
    )


async def _start_web():
    app = web.Application()
    app.router.add_get("/", _handle_ping)
    app.router.add_get("/health", _handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    log.info("Web server ouvindo em 0.0.0.0:%d", PORT)


# ───────────────────────── Entrypoint ─────────────────────────
async def main():
    if not TOKEN:
        raise SystemExit("DISCORD_TOKEN não definido!")
    await _start_web()
    async with bot:
        await bot.start(TOKEN)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Encerrando…")
