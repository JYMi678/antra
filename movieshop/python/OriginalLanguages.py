# Databricks notebook source
# MAGIC %md
# MAGIC ### Create OriginalLanguages silver table

# COMMAND ----------

# MAGIC %run "./includes/configuration"

# COMMAND ----------

# MAGIC  %run "./includes/utilities"

# COMMAND ----------

dbutils.fs.rm(f"{bronze_folder_path}/originallanguages", recurse=True)
dbutils.fs.rm(f"{silver_folder_path}/originallanguages", recurse=True)

# COMMAND ----------

# MAGIC %md
# MAGIC #### raw to bronze

# COMMAND ----------

raw_df = read_batch_raw(raw_folder_path)

transformed_raw_df = transform_raw(raw_df)

raw_to_bronze = batch_writer( dataframe=transformed_raw_df )
raw_to_bronze.save(f"{bronze_folder_path}/originallanguages")


# COMMAND ----------

spark.sql("""
drop table if exists OriginalLanguages_bronze
""")

spark.sql(f"""
create table OriginalLanguages_bronze
using delta 
location "{bronze_folder_path}/originallanguages"
""")

# COMMAND ----------

# MAGIC %sql
# MAGIC 
# MAGIC select * from OriginalLanguages_bronze

# COMMAND ----------

# MAGIC %md
# MAGIC #### bronze to silver

# COMMAND ----------

silver_originallanguages = spark.read.table("OriginalLanguages_bronze").filter("status = 'new' ")

# COMMAND ----------

silver_originallanguages = silver_originallanguages.select("Movies.Id","Movies.Title", "Movies.OriginalLanguage","Movies")

# COMMAND ----------

silver_originallanguages = silver_originallanguages.select(
    col("Id").cast("integer").alias("movie_id"),
    col("Title").alias("title"),
    col("OriginalLanguage").alias("original_languages"),
    col("Movies")
)

# COMMAND ----------

silver_originallanguages.count()

# COMMAND ----------

silver_originallanguages = silver_originallanguages.drop_duplicates()

# COMMAND ----------

silver_originallanguages.count()

# COMMAND ----------

silver_originallanguages.na.drop().count() #TO SEE IF NEED quarentine

# COMMAND ----------

silver_originallanguages_clean = silver_originallanguages  # assume no quarantine

# COMMAND ----------

bronzeToSilverWriter = batch_writer(dataframe=silver_originallanguages_clean, exclude_columns=["Movies"])
bronzeToSilverWriter.save(f"{silver_folder_path}/originallanguages")

# COMMAND ----------

#
delta_originallanguages = read_batch_delta(f"{silver_folder_path}/originallanguages")
delta_originallanguages = delta_originallanguages.drop_duplicates()
display(delta_originallanguages)

# COMMAND ----------

#
deltaToSilverWriter = batch_writer(dataframe=delta_originallanguages)
deltaToSilverWriter.save(f"{silver_folder_path}/originallanguages")

# COMMAND ----------

spark.sql("""
drop table if exists originallanguages_delta
""")

spark.sql(f"""
create table originallanguages_delta
using delta 
location "{silver_folder_path}/originallanguages"
""")

# COMMAND ----------

# MAGIC %sql
# MAGIC select * from originallanguages_delta order by movie_id

# COMMAND ----------

from delta.tables import DeltaTable

bronzeTable = DeltaTable.forPath(spark, f"{bronze_folder_path}/originallanguages")
silverAugmented = (
    silver_originallanguages_clean
    .withColumn("status", lit("loaded"))
)

update_match = "o_bronze.Movies = clean.Movies"
update = {"status": "clean.status"}

(
  bronzeTable.alias("o_bronze")
  .merge(silverAugmented.alias("clean"), update_match)
  .whenMatchedUpdate(set=update)
  .execute()
)
