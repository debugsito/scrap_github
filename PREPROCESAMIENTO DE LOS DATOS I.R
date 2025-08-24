############ PREPROCESAMIENTO DE LOS DATOS ########

## Librerias
library(tidyr)
library(dplyr)
#install.packages("pairs")
library(corrplot)
library(naniar)

######################################### 1. Carga de Datos

### Lectura y creación de archivos ###

# Ubicación de la carpeta 
b <- 'C:\\CynthiaDiscoN\\Cynthia\\ESAN\\Minería de datos\\semestre 2024II\\2.- PREPROCESAMIENTO DE LOS DATOS'
setwd(b)

"Emisiones de contaminantes atmosféricos por fuentes fijas, 2008 (Toneladas)
Contaminante
1) Estado_emergencia: Ciudades en estado de emergencia por contaminantes.
2) PM10: partículas iguales o menores a 10 micrómetros 
3) PM2.5: partículas iguales o menores a 2.5 micrómetros 
4) S02 : dióxido de azufre 
5) CO: monóxido de carbono
6) NOx: óxidos de nitrógeno 
7) COV: compuestos orgánicos volátiles 
8) NH3 : amoniaco 
9) CN: Carbono Negro"

# Importar archivo
niveles <- read.csv(file = "Niveles de contaminacion.csv", na.strings = "",header = TRUE, sep = ";", dec = ";",) #row.names = 1) #No tiene nombres en las filas

data <- niveles

# Visualizar las primeras filas
head(data)

#####################################  2. Exploración de los Datos

# Revisar la estructura de los datos
str(data)

# Resumen estadístico de las columnas numéricas
summary(data)

# Scatterplot matrix para visualizar las relaciones entre todas las variables
# Filtrar solo columnas numéricas
data_numerico <- data %>% select(where(is.numeric))

# Crear la matriz de dispersión
pairs(data_numerico)

# Correlación entre las variables numéricas
correlation_matrix <- cor(data_numerico, use = "complete.obs")
print(correlation_matrix)

correlacion<-round(cor(correlation_matrix), 1)
corrplot(correlacion, method="number", type="upper")

# Histograma de la variable PM10
hist(data_numerico$PM10, 
     xlab = "PM10", ylab = "Frecuencia",
     main = "Distribución de PM10")

# Boxplot de la variable SO2 para identificar valores atípicos
boxplot(data_numerico$SO2, 
        xlab = "", ylab = "SO2",
        main = "Boxplot de SO2")
#################################### 3. Identificación de Valores Faltantes

# Identificar valores faltantes
missing_values <- sapply(data, function(x) sum(is.na(x)))

# Porcentaje de valores faltantes
missing_percent <- sapply(data, function(x) mean(is.na(x))) * 100

# Crear un data frame con la información
missing_data <- data.frame(
  Column = names(missing_values),
  Missing_Values = missing_values,
  Missing_Percent = missing_percent
)

# Mostrar columnas con valores faltantes
missing_data <- missing_data %>% filter(Missing_Values > 0)
print(missing_data)


# Crear la visualización de valores faltantes
vis_miss(data)
################################### 4. Tratamiento de Valores Faltantes

# Eliminar filas con valores faltantes
data_clean <- data %>% drop_na() ;data_clean

# O eliminar columnas con demasiados valores faltantes (por ejemplo, más del 25%)
data_clean <- data %>% select(-one_of(names(data)[missing_percent > 25])); data_clean


# Función para calcular la moda
get_mode <- function(v) {
  uniqv <- unique(v)
  uniqv[which.max(tabulate(match(v, uniqv)))]
}

# Imputación para columnas numéricas con la mediana y para columnas categóricas con la moda
data_imputed <- data %>%
  # Imputación de variables numéricas con la mediana
  mutate(across(where(is.numeric), ~ ifelse(is.na(.), median(., na.rm = TRUE), .))) %>%
  # Imputación de variables categóricas con la moda
  mutate(across(where(is.factor) | where(is.character), ~ ifelse(is.na(.), get_mode(.), .)))

############################################# Resultado Final

# Verificar el resultado final
summary(data_imputed)  # O data_clean dependiendo del tratamiento elegido
data_imputed


## /// Otro metodo de imputación (Vecinos más cercanos)

# Instalar y cargar los paquetes necesarios
#install.packages("VIM")
library(VIM)
library(dplyr)


# Imputación final utilizando KNN para cualquier dato faltante restante
data_imputed_knn <- kNN(data, k = 5)

# Eliminar columnas auxiliares creadas por kNN
data_imputed_knn <- data_imputed_knn[, !grepl("_imp$", names(data_imputed_knn))]

# Ver el resumen de los datos imputados
summary(data_imputed_knn); data_imputed_knn

