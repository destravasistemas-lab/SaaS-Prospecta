"""
Importa a base pública de CNPJ da Receita Federal para a prospecção.

Uso:
    DATABASE_URL=postgresql://... python scripts/import_cnpj.py --ufs PB,PE,RN
    (opcional) --month 2026-11   (padrão: o mês mais recente publicado)

Carrega só empresas ATIVAS dos estados escolhidos que tenham telefone ou
e-mail. Monta a tabela nova ao lado e troca no fim, então o app continua
funcionando durante a importação. Cada estado grande (ex.: SP) ocupa alguns GB.
"""
import argparse
import asyncio
import csv
import io
import os
import re
import sys
import tempfile
import unicodedata
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import asyncpg
import httpx

SHARE = "YggdBLfdninEJX9"
WEBDAV = "https://arquivos.receitafederal.gov.br/public.php/webdav"
BATCH = 20_000
ATIVA = "02"

COMPANY_COLUMNS = [
    "cnpj", "razao_social", "nome_fantasia", "cnae", "cnaes_secundarios", "uf", "municipio_code",
    "bairro", "endereco", "cep", "telefone1", "telefone2", "email", "porte", "mei", "abertura",
]


def normalize_search(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", text.lower()).strip()


def clean(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def phone(ddd: str, number: str) -> str | None:
    ddd = re.sub(r"\D", "", ddd or "").lstrip("0")
    number = re.sub(r"\D", "", number or "")
    if len(ddd) == 2 and len(number) in (8, 9):
        return f"55{ddd}{number}"
    return None


def strip_cpf(name: str | None) -> str | None:
    """Empresário individual/MEI: a razão social traz o CPF no fim. Não guardamos."""
    if not name:
        return None
    return re.sub(r"[\s.-]*\d{3}\.?\d{3}\.?\d{3}-?\d{2}\s*$", "", name).strip() or None


def parse_estabelecimento(row: list[str], ufs: set[str]) -> tuple | None:
    if len(row) < 28 or row[5] != ATIVA or row[19] not in ufs:
        return None
    tel1 = phone(row[21], row[22])
    tel2 = phone(row[23], row[24])
    if not tel1 and tel2:
        tel1, tel2 = tel2, None
    email = clean(row[27])
    email = email.lower() if email and "@" in email else None
    if not tel1 and not email:
        return None
    rua = " ".join(p for p in (clean(row[13]), clean(row[14])) if p)
    endereco = ", ".join(p for p in (rua, clean(row[15]), clean(row[16])) if p) or None
    secundarios = [c for c in (row[12] or "").split(",") if c.strip()]
    return (
        f"{row[0]}{row[1]}{row[2]}",
        None,
        clean(row[4]),
        row[11][:7],
        f",{','.join(secundarios)}," if secundarios else None,
        row[19],
        row[20].zfill(4),
        clean(row[17]),
        (endereco or "")[:255] or None,
        clean(row[18]),
        tel1,
        tel2,
        (email or "")[:255] or None,
        None,
        False,
        clean(row[10]),
    )


def rows(zip_path: Path):
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            with zf.open(name) as raw:
                yield from csv.reader(io.TextIOWrapper(raw, encoding="latin-1", newline=""), delimiter=";", quotechar='"')


async def latest_month(client: httpx.AsyncClient) -> str:
    r = await client.request("PROPFIND", f"{WEBDAV}/", headers={"Depth": "1"}, auth=(SHARE, ""))
    months = sorted(set(re.findall(r"/public\.php/webdav/(\d{4}-\d{2})/", r.text)))
    if not months:
        sys.exit("Não encontrei nenhum mês publicado na Receita.")
    return months[-1]


async def download(client: httpx.AsyncClient, month: str, name: str, folder: Path) -> Path:
    target = folder / name
    async with client.stream("GET", f"{WEBDAV}/{month}/{name}", auth=(SHARE, "")) as r:
        r.raise_for_status()
        with open(target, "wb") as f:
            async for chunk in r.aiter_bytes(1 << 20):
                f.write(chunk)
    print(f"  baixado {name} ({target.stat().st_size / 1e6:.0f} MB)", flush=True)
    return target


async def copy_batches(conn, table: str, columns: list[str], records):
    batch, total = [], 0
    for rec in records:
        batch.append(rec)
        if len(batch) >= BATCH:
            await conn.copy_records_to_table(table, records=batch, columns=columns)
            total += len(batch)
            batch = []
    if batch:
        await conn.copy_records_to_table(table, records=batch, columns=columns)
        total += len(batch)
    return total


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ufs", required=True, help="Estados separados por vírgula, ex.: PB,PE")
    parser.add_argument("--month", help="AAAA-MM (padrão: o mais recente)")
    args = parser.parse_args()
    ufs = {u.strip().upper() for u in args.ufs.split(",") if u.strip()}
    dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")

    async with httpx.AsyncClient(timeout=httpx.Timeout(60, read=600), follow_redirects=True) as client:
        month = args.month or await latest_month(client)
        print(f"Receita {month}, estados {sorted(ufs)}", flush=True)
        conn = await asyncpg.connect(dsn)
        try:
            await conn.execute("""
                DROP TABLE IF EXISTS cnpj_companies_new;
                CREATE TABLE cnpj_companies_new (
                    cnpj VARCHAR(14) NOT NULL, razao_social VARCHAR(255), nome_fantasia VARCHAR(255),
                    cnae VARCHAR(7) NOT NULL, cnaes_secundarios TEXT, uf VARCHAR(2) NOT NULL,
                    municipio_code VARCHAR(4) NOT NULL, bairro VARCHAR(120), endereco VARCHAR(255),
                    cep VARCHAR(8), telefone1 VARCHAR(15), telefone2 VARCHAR(15), email VARCHAR(255),
                    porte VARCHAR(2), mei BOOLEAN NOT NULL DEFAULT FALSE, abertura VARCHAR(8)
                );
                DROP TABLE IF EXISTS cnpj_empresas_tmp; CREATE TABLE cnpj_empresas_tmp (basico VARCHAR(8), razao VARCHAR(255), porte VARCHAR(2));
                DROP TABLE IF EXISTS cnpj_mei_tmp; CREATE TABLE cnpj_mei_tmp (basico VARCHAR(8));
            """)
            with tempfile.TemporaryDirectory() as tmp:
                folder = Path(tmp)

                cnaes = [(r[0].zfill(7), r[1].strip()[:255], normalize_search(r[1])[:255])
                         for r in rows(await download(client, month, "Cnaes.zip", folder)) if len(r) >= 2]
                municipios = {r[0].zfill(4): r[1].strip().title() for r in rows(await download(client, month, "Municipios.zip", folder)) if len(r) >= 2}

                basicos: set[str] = set()
                city_uf: dict[str, str] = {}
                total = 0
                for i in range(10):
                    path = await download(client, month, f"Estabelecimentos{i}.zip", folder)

                    def wanted():
                        for row in rows(path):
                            rec = parse_estabelecimento(row, ufs)
                            if rec:
                                basicos.add(rec[0][:8])
                                city_uf[rec[6]] = rec[5]
                                yield rec

                    total += await copy_batches(conn, "cnpj_companies_new", COMPANY_COLUMNS, wanted())
                    path.unlink()
                    print(f"  empresas ativas com contato até agora: {total}", flush=True)

                for i in range(10):
                    path = await download(client, month, f"Empresas{i}.zip", folder)
                    await copy_batches(conn, "cnpj_empresas_tmp", ["basico", "razao", "porte"], (
                        (r[0], (strip_cpf(r[1]) or "")[:255] or None, clean(r[5]))
                        for r in rows(path) if len(r) >= 6 and r[0] in basicos
                    ))
                    path.unlink()

                path = await download(client, month, "Simples.zip", folder)
                await copy_batches(conn, "cnpj_mei_tmp", ["basico"], (
                    (r[0],) for r in rows(path) if len(r) >= 5 and r[0] in basicos and r[4] == "S"
                ))
                path.unlink()

            print("Montando índices…", flush=True)
            await conn.execute("""
                CREATE INDEX ix_cnpj_empresas_tmp ON cnpj_empresas_tmp (basico);
                UPDATE cnpj_companies_new c SET razao_social = e.razao, porte = e.porte
                  FROM cnpj_empresas_tmp e WHERE e.basico = left(c.cnpj, 8);
                UPDATE cnpj_companies_new c SET mei = TRUE
                  FROM cnpj_mei_tmp m WHERE m.basico = left(c.cnpj, 8);
                ALTER TABLE cnpj_companies_new ADD CONSTRAINT cnpj_companies_new_pkey PRIMARY KEY (cnpj);
                CREATE INDEX ix_cnpj_companies_new_busca ON cnpj_companies_new (municipio_code, cnae);
                CREATE INDEX ix_cnpj_companies_new_cnae ON cnpj_companies_new (cnae);
                DROP TABLE cnpj_empresas_tmp; DROP TABLE cnpj_mei_tmp;
            """)

            async with conn.transaction():
                await conn.execute("""
                    DROP TABLE IF EXISTS cnpj_companies;
                    ALTER TABLE cnpj_companies_new RENAME TO cnpj_companies;
                    ALTER TABLE cnpj_companies RENAME CONSTRAINT cnpj_companies_new_pkey TO cnpj_companies_pkey;
                    ALTER INDEX ix_cnpj_companies_new_busca RENAME TO ix_cnpj_companies_busca;
                    ALTER INDEX ix_cnpj_companies_new_cnae RENAME TO ix_cnpj_companies_cnae;
                    CREATE TABLE IF NOT EXISTS cnpj_cnaes (code VARCHAR(7) PRIMARY KEY, description VARCHAR(255) NOT NULL, search VARCHAR(255) NOT NULL);
                    CREATE TABLE IF NOT EXISTS cnpj_municipios (code VARCHAR(4) PRIMARY KEY, name VARCHAR(120) NOT NULL, uf VARCHAR(2), search VARCHAR(120) NOT NULL);
                    CREATE TABLE IF NOT EXISTS cnpj_import_info (id INTEGER PRIMARY KEY, reference_month VARCHAR(7) NOT NULL, ufs VARCHAR(120) NOT NULL, total INTEGER NOT NULL, imported_at TIMESTAMPTZ);
                    TRUNCATE cnpj_cnaes; TRUNCATE cnpj_municipios;
                """)
                await conn.copy_records_to_table("cnpj_cnaes", records=cnaes, columns=["code", "description", "search"])
                await conn.copy_records_to_table("cnpj_municipios", columns=["code", "name", "uf", "search"], records=[
                    (code, name, city_uf.get(code), normalize_search(name)) for code, name in municipios.items()
                ])
                await conn.execute("""
                    INSERT INTO cnpj_import_info (id, reference_month, ufs, total, imported_at)
                    VALUES (1, $1, $2, $3, $4)
                    ON CONFLICT (id) DO UPDATE SET reference_month = $1, ufs = $2, total = $3, imported_at = $4
                """, month, ",".join(sorted(ufs)), total, datetime.now(timezone.utc))
            await conn.execute("ANALYZE cnpj_companies")
            print(f"Pronto: {total} empresas de {sorted(ufs)} (Receita {month}).", flush=True)
        finally:
            await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
