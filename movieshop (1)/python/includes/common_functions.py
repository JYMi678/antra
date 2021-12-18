# Databricks notebook source
from pyspark.sql.types import StructType, StructField, IntegerType, StringType, DoubleType, DateType, LongType, TimestampType
from delta.tables import DeltaTable
from pyspark.sql import DataFrame
from pyspark.sql.functions import (
    col,
    current_timestamp,
    from_json,
    from_unixtime,
    lag,
    lead,
    lit,
    mean,
    stddev,
    max,
    explode,
    when,
    abs
)
from typing import List
from pyspark.sql.session import SparkSession
from pyspark.sql.window import Window

# COMMAND ----------

def batch_writer(
    dataframe: DataFrame,
    exclude_columns: List = [],
    mode: str = "append",
) -> DataFrame:
    return (
        dataframe.drop(
            *exclude_columns
        )  # This uses Python argument unpacking (https://docs.python.org/3/tutorial/controlflow.html#unpacking-argument-lists)
        .write.format("delta")
        .mode(mode)
    )


# COMMAND ----------

def read_batch_raw(raw_folder_path: str) -> DataFrame:
    return spark.read.option("multiline", True).option("inferSchema", "true").json("/mnt/movieshopdl/raw/movieshop").select(explode("movie").alias("movies"))


# COMMAND ----------

def transform_raw(raw: DataFrame) -> DataFrame:
    return raw.withColumn("data_source", lit("movieshop_final_project")).withColumn("ingest_time", current_timestamp()).withColumn("status", lit("new")).withColumn("ingest_date", current_timestamp().cast("date"))
        

# COMMAND ----------

def read_movies_bronze() -> DataFrame:
    return spark.read.table("movies_bronze").filter("status = 'new' ")

# COMMAND ----------

def read_genres_bronze() -> DataFrame:
    return spark.read.load(f"{bronze_folder_path}/genres").filter("status = 'new' ").silver_genres.select(explode("Movies.genres").alias("genres"),"Movies")

# COMMAND ----------

def read_batch_delta(deltaPath: str) -> DataFrame:
    return spark.read.format("delta").load(deltaPath)

# COMMAND ----------

def transform_movies_bronze(bronze: DataFrame, quarantine: bool = False) -> DataFrame:
    
    silver_movies = bronze.select("Movies.Id","Movies.Title", "Movies.Overview", "Movies.Budget", "Movies.RunTime", "Movies")
    
    silver_movies = silver_movies.withColumn("Budget",when(col("Budget")<=1000000 ,1000000).otherwise(silver_movies.Budget))
    
    silver_movies = silver_movies.dropDuplicates()
    
    
    if not quarantine:
        silver_movies = silver_movies.select(
            col("Id").cast("integer").alias("movie_id"),
            col("Title").alias("title"),
            col("Overview").alias("overview"),
            col("Budget").alias("budget"),
            col("RunTime").cast("integer").alias("runtime"),
            col("Movies")
        )
    else:
        silver_movies = silver_movies.select(
            col("Id").cast("integer").alias("movie_id"),
            col("Title").alias("title"),
            col("Overview").alias("overview"),
            col("Budget").alias("budget"),
            abs(col("RunTime")).cast("integer").alias("runtime"),
            col("Movies")
        )

    return silver_movies

# COMMAND ----------

def generate_clean_and_quarantine_dataframes(
    dataframe: DataFrame,
) -> (DataFrame, DataFrame):
    return (
        dataframe.filter("runtime >= 0"),
        dataframe.filter("runtime < 0"),
    )


# COMMAND ----------

def update_bronze_movies_status(
    spark: SparkSession, bronzeTablePath: str, dataframe: DataFrame, status: str
) -> bool:

    bronzeTable = DeltaTable.forPath(spark, bronzeTablePath)
    dataframeAugmented = dataframe.withColumn("status", lit(status))

    update_match = "m_bronze.Movies = dataframe.Movies"
    update = {"status": "dataframe.status"}

    (
        bronzeTable.alias("m_bronze")
        .merge(dataframeAugmented.alias("dataframe"), update_match)
        .whenMatchedUpdate(set=update)
        .execute()
    )

    return True

# COMMAND ----------

def update_bronze_originallanguage_status(
    spark: SparkSession, bronzeTablePath: str, dataframe: DataFrame, status: str
) -> bool:

    bronzeTable = DeltaTable.forPath(spark, bronzeTablePath)
    dataframeAugmented = dataframe.withColumn("status", lit(status))

    update_match = "o_bronze.Movies = dataframe.Movies"
    update = {"status": "dataframe.status"}

    (
        bronzeTable.alias("o_bronze")
        .merge(dataframeAugmented.alias("dataframe"), update_match)
        .whenMatchedUpdate(set=update)
        .execute()
    )

    return True

# COMMAND ----------

# MAGIC %md
# MAGIC def transform_originallanguages_bronze(bronze: DataFrame) -> DataFrame:
# MAGIC     
# MAGIC     silver_originallanguages = spark.read.table("OriginalLanguages_bronze").filter("status = 'new' ")
# MAGIC     silver_originallanguages = silver_originallanguages.select("Movies.Id","Movies.Title", "Movies.OriginalLanguages","Movies")
# MAGIC     
# MAGIC     silver_originallanguages = silver_originallanguages.drop_duplicates()
# MAGIC     
# MAGIC     silver_originallanguages = silver_originallanguages.select(
# MAGIC         col("Id").cast("integer").alias("movie_id"),
# MAGIC         col("Title").alias("title"),
# MAGIC         col("OriginalLanguages").alias("original_languages"),
# MAGIC         col("Movies")
# MAGIC      )
# MAGIC 
# MAGIC     return silver_originallanguages

# COMMAND ----------

# MAGIC %md
# MAGIC def transform_genres_bronze(bronze: DataFrame) -> DataFrame:
# MAGIC     
# MAGIC     silver_genres = spark.read.table("genres_bronze").filter("status = 'new' ")
# MAGIC     silver_genres = silver_genres.select(explode("Movies.genres").alias("genres"),"Movies")
# MAGIC     silver_genres = silver_genres.select("genres.id","genres.name","movies")
# MAGIC     
# MAGIC     
# MAGIC     silver_genres = silver_genres.select(
# MAGIC         col("id").cast("integer").alias("genre_id"),
# MAGIC         col("name").alias("genre_name"),
# MAGIC         col("Movies")
# MAGIC     )
# MAGIC     
# MAGIC     silver_genres = silver_genres.drop_duplicates("genre_id").dropna()#bug
# MAGIC 
# MAGIC     return silver_genres
