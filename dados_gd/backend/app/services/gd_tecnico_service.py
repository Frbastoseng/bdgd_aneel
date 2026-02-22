"""Serviço de consulta de dados técnicos das usinas GD."""

import logging
from typing import List, Dict, Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gd_tecnico import (
    GDTecnicoSolar,
    GDTecnicoEolica,
    GDTecnicoHidraulica,
    GDTecnicoTermica,
)

logger = logging.getLogger(__name__)


def _solar_to_dict(item: GDTecnicoSolar) -> Dict[str, Any]:
    return {
        "tipo": "solar",
        "cod_geracao_distribuida": item.cod_geracao_distribuida,
        "mda_area_arranjo": float(item.mda_area_arranjo) if item.mda_area_arranjo else None,
        "mda_potencia_instalada": float(item.mda_potencia_instalada) if item.mda_potencia_instalada else None,
        "nom_fabricante_modulo": item.nom_fabricante_modulo,
        "nom_modelo_modulo": item.nom_modelo_modulo,
        "nom_fabricante_inversor": item.nom_fabricante_inversor,
        "nom_modelo_inversor": item.nom_modelo_inversor,
        "qtd_modulos": item.qtd_modulos,
        "mda_potencia_modulos": float(item.mda_potencia_modulos) if item.mda_potencia_modulos else None,
        "mda_potencia_inversores": float(item.mda_potencia_inversores) if item.mda_potencia_inversores else None,
        "dat_conexao": item.dat_conexao.isoformat() if item.dat_conexao else None,
    }


def _eolica_to_dict(item: GDTecnicoEolica) -> Dict[str, Any]:
    return {
        "tipo": "eolica",
        "cod_geracao_distribuida": item.cod_geracao_distribuida,
        "nom_fabricante_aerogerador": item.nom_fabricante_aerogerador,
        "dsc_modelo_aerogerador": item.dsc_modelo_aerogerador,
        "mda_potencia_instalada": float(item.mda_potencia_instalada) if item.mda_potencia_instalada else None,
        "mda_altura_pa": float(item.mda_altura_pa) if item.mda_altura_pa else None,
        "idc_eixo_rotor": item.idc_eixo_rotor,
        "dat_conexao": item.dat_conexao.isoformat() if item.dat_conexao else None,
    }


def _hidraulica_to_dict(item: GDTecnicoHidraulica) -> Dict[str, Any]:
    return {
        "tipo": "hidraulica",
        "cod_geracao_distribuida": item.cod_geracao_distribuida,
        "nom_rio": item.nom_rio,
        "mda_potencia_instalada": float(item.mda_potencia_instalada) if item.mda_potencia_instalada else None,
        "mda_potencia_aparente": float(item.mda_potencia_aparente) if item.mda_potencia_aparente else None,
        "mda_fator_potencia": float(item.mda_fator_potencia) if item.mda_fator_potencia else None,
        "mda_tensao": float(item.mda_tensao) if item.mda_tensao else None,
        "mda_nivel_operacional_montante": float(item.mda_nivel_operacional_montante) if item.mda_nivel_operacional_montante else None,
        "mda_nivel_operacional_jusante": float(item.mda_nivel_operacional_jusante) if item.mda_nivel_operacional_jusante else None,
        "dat_conexao": item.dat_conexao.isoformat() if item.dat_conexao else None,
    }


def _termica_to_dict(item: GDTecnicoTermica) -> Dict[str, Any]:
    return {
        "tipo": "termica",
        "cod_geracao_distribuida": item.cod_geracao_distribuida,
        "mda_potencia_instalada": float(item.mda_potencia_instalada) if item.mda_potencia_instalada else None,
        "dat_conexao": item.dat_conexao.isoformat() if item.dat_conexao else None,
        "dsc_ciclo_termodinamico": item.dsc_ciclo_termodinamico,
        "dsc_maquina_motriz": item.dsc_maquina_motriz,
    }


class GDTecnicoService:
    """Serviço para consultas de dados técnicos das usinas GD."""

    @staticmethod
    async def buscar_por_codigos(db: AsyncSession, codigos: List[str]) -> Dict[str, Dict[str, Any]]:
        """Busca dados técnicos nas 4 tabelas por lista de cod_geracao_distribuida.
        Retorna dict {cod: {tipo, ...dados_tecnicos}} para os encontrados."""
        if not codigos:
            return {}

        result_map: Dict[str, Dict[str, Any]] = {}

        # Solar (maior tabela - query principal)
        result = await db.execute(
            select(GDTecnicoSolar).where(
                GDTecnicoSolar.cod_geracao_distribuida.in_(codigos)
            )
        )
        for item in result.scalars().all():
            result_map[item.cod_geracao_distribuida] = _solar_to_dict(item)

        # Códigos ainda não encontrados
        remaining = [c for c in codigos if c not in result_map]

        # Eólica
        if remaining:
            result = await db.execute(
                select(GDTecnicoEolica).where(
                    GDTecnicoEolica.cod_geracao_distribuida.in_(remaining)
                )
            )
            for item in result.scalars().all():
                result_map[item.cod_geracao_distribuida] = _eolica_to_dict(item)
            remaining = [c for c in remaining if c not in result_map]

        # Hidráulica
        if remaining:
            result = await db.execute(
                select(GDTecnicoHidraulica).where(
                    GDTecnicoHidraulica.cod_geracao_distribuida.in_(remaining)
                )
            )
            for item in result.scalars().all():
                result_map[item.cod_geracao_distribuida] = _hidraulica_to_dict(item)
            remaining = [c for c in remaining if c not in result_map]

        # Térmica
        if remaining:
            result = await db.execute(
                select(GDTecnicoTermica).where(
                    GDTecnicoTermica.cod_geracao_distribuida.in_(remaining)
                )
            )
            for item in result.scalars().all():
                result_map[item.cod_geracao_distribuida] = _termica_to_dict(item)

        return result_map
