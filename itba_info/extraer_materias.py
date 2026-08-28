#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
from pathlib import Path
import pandas as pd

CSV_GRANDE = "materias_completo.csv"
TXT_MATERIAS = "materias_objetivo.txt"
CSV_SALIDA = "materias_filtradas_detallado.csv"


def extraer_materias_objetivo(texto: str):
    materias = []
    vistos = set()

    patron = re.compile(r'^\s*(\d{2}\.\d{2})\s*-\s*(.+?)\s*(?:\t|\s{2,}|\d+\s|$)')

    for line in texto.splitlines():
        line = line.strip()
        if not line:
            continue

        m = patron.match(line)
        if m:
            codigo = m.group(1).strip()
            nombre = m.group(2).strip()
            nombre = re.sub(r'\s+\d+\s*$', '', nombre).strip()

            if codigo not in vistos:
                materias.append({
                    "codigo": codigo,
                    "nombre_objetivo": nombre
                })
                vistos.add(codigo)

    return pd.DataFrame(materias)


def limpiar_codigo(x):
    if pd.isna(x):
        return None
    s = str(x).strip()
    m = re.search(r'(\d{2}\.\d{2})', s)
    return m.group(1) if m else s


def limpiar_texto(x):
    if pd.isna(x):
        return ""
    return str(x).strip()


def elegir_columna(df, candidatas, obligatoria=True):
    for c in candidatas:
        if c in df.columns:
            return c
    if obligatoria:
        raise ValueError(f"No encontré ninguna de estas columnas: {candidatas}")
    return None


def main():
    texto = Path(TXT_MATERIAS).read_text(encoding="utf-8")
    df_obj = extraer_materias_objetivo(texto)

    if df_obj.empty:
        raise ValueError("No pude extraer materias del TXT objetivo")

    df_big = pd.read_csv(CSV_GRANDE, dtype=str).fillna("")

    col_codigo = elegir_columna(df_big, ["Códigos", "Codigos"])
    col_materia = elegir_columna(df_big, ["Materia"])
    col_link = elegir_columna(df_big, ["Link", "Hipervínculo PDF Actualizado", "Hipervinculo PDF Actualizado"], obligatoria=False)

    col_cont_min = elegir_columna(df_big, ["Contenidos mínimos", "Contenidos minimos"], obligatoria=False)
    col_obj = elegir_columna(df_big, ["Objetivos de aprendizaje"], obligatoria=False)
    col_cont_titulo = elegir_columna(df_big, ["Contenidos - Título", "Contenidos - Titulo"], obligatoria=False)
    col_cont_desc = elegir_columna(df_big, ["Contenidos - Descripción", "Contenidos - Descripcion"], obligatoria=False)
    col_act_desc = elegir_columna(df_big, ["Actividades - Descripción", "Actividades - Descripcion"], obligatoria=False)

    df_big["codigo"] = df_big[col_codigo].map(limpiar_codigo)
    df_big["nombre_sheet"] = df_big[col_materia].map(limpiar_texto)
    df_big["link"] = df_big[col_link].map(limpiar_texto) if col_link else ""

    df_big["contenidos_minimos"] = df_big[col_cont_min].map(limpiar_texto) if col_cont_min else ""
    df_big["objetivos_aprendizaje"] = df_big[col_obj].map(limpiar_texto) if col_obj else ""
    df_big["contenidos_titulo"] = df_big[col_cont_titulo].map(limpiar_texto) if col_cont_titulo else ""
    df_big["contenidos_descripcion"] = df_big[col_cont_desc].map(limpiar_texto) if col_cont_desc else ""
    df_big["actividades_descripcion"] = df_big[col_act_desc].map(limpiar_texto) if col_act_desc else ""

    df_big_small = df_big[
        [
            "codigo",
            "nombre_sheet",
            "link",
            "contenidos_minimos",
            "objetivos_aprendizaje",
            "contenidos_titulo",
            "contenidos_descripcion",
            "actividades_descripcion",
        ]
    ].copy()

    # priorizar fila con link si hay duplicados de código
    df_big_small["tiene_link"] = df_big_small["link"].astype(str).str.strip().str.len() > 0
    df_big_small = df_big_small.sort_values(["codigo", "tiene_link"], ascending=[True, False])
    df_big_small = df_big_small.drop_duplicates(subset=["codigo"], keep="first")
    df_big_small = df_big_small.drop(columns=["tiene_link"])

    df_out = df_obj.merge(df_big_small, on="codigo", how="left")

    df_out["nombre"] = df_out["nombre_sheet"].where(
        df_out["nombre_sheet"].fillna("").str.strip() != "",
        df_out["nombre_objetivo"]
    )

    df_out = df_out[
        [
            "codigo",
            "nombre",
            "link",
            "contenidos_minimos",
            "objetivos_aprendizaje",
            "contenidos_titulo",
            "contenidos_descripcion",
            "actividades_descripcion",
        ]
    ].copy()

    df_out = df_out.sort_values("codigo")
    df_out.to_csv(CSV_SALIDA, index=False, encoding="utf-8-sig")

    encontrados = (df_out["link"].fillna("").str.strip() != "").sum()
    total = len(df_out)

    print(f"OK. Archivo generado: {CSV_SALIDA}")
    print(f"Materias objetivo: {total}")
    print(f"Con link encontrado: {encontrados}")
    print(f"Sin link: {total - encontrados}")

    faltantes = df_out[df_out["link"].fillna("").str.strip() == ""]
    if not faltantes.empty:
        print("\nMaterias sin link encontrado:")
        for _, row in faltantes.iterrows():
            print(f"- {row['codigo']} - {row['nombre']}")

    # además, exportar solo faltantes con detalle
    csv_faltantes = "materias_sin_link_detalle.csv"
    faltantes.to_csv(csv_faltantes, index=False, encoding="utf-8-sig")
    print(f"\nArchivo adicional generado: {csv_faltantes}")


if __name__ == "__main__":
    main()
