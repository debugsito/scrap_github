# GitHub Repository Scraper - Detección de Información Sensible

Sistema automatizado para detectar credenciales y secretos expuestos en repositorios públicos de GitHub mediante técnicas de web scraping y análisis de datos.

## El Problema

Miles de desarrolladores publican accidentalmente credenciales de acceso, claves API y tokens en archivos como `.env` o `config.json`. Una vez expuestos en GitHub, estos secretos pueden ser explotados por atacantes para acceder a sistemas críticos.

**Casos reales:**
- **Uber (2014)**: Credenciales expuestas llevaron al compromiso de datos de 50,000 conductores
- **Amazon**: Más de 10,000 claves AWS encontradas en repositorios públicos, usadas para minería de criptomonedas

## La Solución

Este proyecto combina técnicas tradicionales (regex, entropía) con machine learning para clasificar archivos como:
- **Sensibles**: Contienen credenciales reales
- **No sensibles**: Ejemplos, tests o código sin riesgo

**Objetivo**: Reducir falsos positivos y mejorar la detección automática de secretos expuestos.

## Arquitectura

### Fase 1: Búsqueda Masiva
Recolecta repositorios que contengan archivos críticos:
- Archivos de configuración (`.env`, `config.json`, `settings.py`)
- Credenciales (`aws-credentials`, certificados SSH)
- Configuraciones de servicios (Docker, Kubernetes, Terraform)

### Fase 2: Análisis de Contenido
Extrae y analiza el contenido real de archivos sensibles:
- Descarga contenido de archivos críticos
- Calcula entropía para detectar strings aleatorios
- Aplica regex para identificar patrones de credenciales
- Clasifica según contexto y ubicación

### Fase 3: Machine Learning (Futuro)
- Etiquetado semi-automático de secretos reales vs ejemplos
- Entrenamiento de modelos para clasificación inteligente
- Reducción de falsos positivos mediante aprendizaje supervisado

## Características Técnicas

### Procesamiento Paralelo
- **Múltiples workers**: Hasta 20 workers para búsqueda masiva
- **Rate limiting inteligente**: Rotación automática entre múltiples tokens de GitHub
- **Escalabilidad**: De 5,000 a 15,000+ requests/hora según número de tokens

### Base de Datos Optimizada
- **PostgreSQL**: Esquema especializado para metadatos de seguridad
- **Índices avanzados**: Optimizados para búsquedas por tipo de secreto y entropía
- **Detección de duplicados**: Prevención automática de recopilación redundante

## Instalación Rápida

```bash
# Clonar repositorio
git clone https://github.com/debugsito/scrap_github.git
cd scrap_github

# Instalar dependencias
pip install -r requirements.txt
```

### Configuración de Base de Datos

#### Opción A: Docker (Recomendada)
```bash
# Configurar base de datos
docker-compose up -d  # PostgreSQL con Docker

# Configurar tokens en .env
GITHUB_TOKEN=ghp_tu_token_principal
GITHUB_TOKEN_2=ghp_token_secundario  # Opcional: más tokens = más velocidad
```

## Uso Básico

```bash
# Búsqueda masiva de repositorios con archivos sensibles
python -m app.main --phase1-only

# Análisis detallado de contenido
python -m app.main --phase2-only

# Proceso completo
python -m app.main

# Ver estadísticas
python -m app.main --stats
```
```

#### Opción B: PostgreSQL Local
```sql
-- Crear base de datos
CREATE DATABASE github_repos;
CREATE USER github_user WITH PASSWORD 'github_pass';
GRANT ALL PRIVILEGES ON DATABASE github_repos TO github_user;
```

### Configuración de Tokens
El archivo `.env` debe contener tus tokens de GitHub:
```env
GITHUB_TOKEN=ghp_tu_token_principal
GITHUB_TOKEN_2=ghp_token_secundario
GITHUB_TOKEN_3=ghp_token_terciario
```

**Importante**: Cada token debe ser de una cuenta diferente para multiplicar los rate limits.

## Uso del Sistema para Investigación de Seguridad

### Comandos Especializados en Detección de Secretos

#### Recolección Masiva de Repositorios con Archivos Sensibles (Fase 1)
```bash
# Búsqueda enfocada en archivos de configuración críticos (50K repos, últimos 3 años)
python -m app.main --phase1-only

# Búsqueda intensiva de repositorios con credenciales expuestas
python -m app.main --phase1-only --max-repos 100000 --max-age 2 --workers-p1 4

# Solo repositorios populares con mayor probabilidad de exposición real
python -m app.main --phase1-only --min-stars 50 --max-repos 20000
```

#### Análisis Detallado de Contenido Sensible (Fase 2)
```bash
# Extracción y análisis de contenido de archivos críticos
python -m app.main --phase2-only

# Análisis paralelo intensivo de secretos y credenciales
python -m app.main --phase2-only --workers 8
```

## Resultados Esperados

Con la configuración estándar:
- **Fase 1**: 30-50K repositorios en 2-4 horas
- **Fase 2**: 1-2K repositorios analizados por hora  
- **Cobertura**: 25+ lenguajes de programación
- **Archivos**: 40+ tipos de configuración diferentes

## Uso Académico

Sistema diseñado exclusivamente para investigación académica sobre:
- Patrones de exposición de credenciales en código abierto
- Desarrollo de algoritmos de detección automática
- Análisis de adopción de buenas prácticas de seguridad
- Generación de datasets para machine learning

**Importante**: Solo accede a información pública y no explota vulnerabilidades encontradas.

## Estructura del Proyecto

```
scrap_github/
├── app/
│   ├── phases/          # Pipeline de detección
│   ├── config.py        # Configuración
│   ├── main.py          # CLI principal
│   └── token_manager.py # Gestión multi-token
├── sql/init.sql         # Schema de BD
└── requirements.txt     # Dependencias


## Agradecimientos

Agradezco a mis compañeros de universidad que proporcionaron tokens adicionales de GitHub para acelerar la recolección de datos.

## Contacto

Para preguntas académicas, sugerencias de mejora o posibles colaboraciones, puedes contactarme a través de csramosflores@gmail.com.

---

**Nota**: Este proyecto es desarrollado como parte de mi trabajo de tesis en Ingeniería de Sistemas. El código y los datos están disponibles únicamente para propósitos académicos y de investigación.