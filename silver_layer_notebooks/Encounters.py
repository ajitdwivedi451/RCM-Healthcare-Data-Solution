# Databricks notebook source
encounter_df1 = spark.read.parquet("abfss://bronze@kaimurservicesdevdata.dfs.core.windows.net/hosa/encounters", header=True)
display(encounter_df1) 

encounter_df2 = spark.read.parquet("abfss://bronze@kaimurservicesdevdata.dfs.core.windows.net/hosb/encounters")

# COMMAND ----------

encounter_df2.display()

# COMMAND ----------

encounter_df1.createOrReplaceTempView("hosa_encounters")
encounter_df2.createOrReplaceTempView("hosb_encounters")

# COMMAND ----------

# MAGIC %sql
# MAGIC Create OR REPLACE TEMP VIEW encounters AS 
# MAGIC SELECT * from hosa_encounters
# MAGIC UNION ALL 
# MAGIC SELECT * from hosb_encounters
# MAGIC ;
# MAGIC Select * from encounters

# COMMAND ----------

"""%sql
-- Create temporary views for the parquet files
CREATE OR REPLACE TEMP VIEW hosa_encounters
USING parquet
OPTIONS (
  path = "abfss://bronze@kaimurservicesdevdata.dfs.core.windows.net/hosa/encounters"
);

CREATE OR REPLACE TEMP VIEW hosb_encounters
USING parquet
OPTIONS (
  path = "abfss://bronze@kaimurservicesdevdata.dfs.core.windows.net/hosb/encounters"
);

-- Union the two views
CREATE OR REPLACE TEMP VIEW encounters AS
SELECT * FROM hosa_encounters
UNION ALL
SELECT * FROM hosb_encounters;

-- Display the merged data
SELECT * FROM encounters;"""

# COMMAND ----------

# MAGIC %sql
# MAGIC --select * from encounters

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE OR REPLACE TEMP VIEW quality_checks AS
# MAGIC SELECT 
# MAGIC concat(EncounterID,'-',datasource) as EncounterID,
# MAGIC EncounterID SRC_EncounterID,
# MAGIC PatientID,
# MAGIC EncounterDate,
# MAGIC EncounterType,
# MAGIC ProviderID,
# MAGIC DepartmentID,
# MAGIC ProcedureCode,
# MAGIC InsertedDate as SRC_InsertedDate,
# MAGIC ModifiedDate as SRC_ModifiedDate,
# MAGIC datasource,
# MAGIC     CASE 
# MAGIC         WHEN EncounterID IS NULL OR PatientID IS NULL THEN TRUE
# MAGIC         ELSE FALSE
# MAGIC     END AS is_quarantined
# MAGIC FROM encounters

# COMMAND ----------

# MAGIC %sql
# MAGIC select * from quality_checks
# MAGIC where datasource='hos-b'

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE TABLE IF NOT EXISTS silver.encounters (
# MAGIC EncounterID string,
# MAGIC SRC_EncounterID string,
# MAGIC PatientID string,
# MAGIC EncounterDate date,
# MAGIC EncounterType string,
# MAGIC ProviderID string,
# MAGIC DepartmentID string,
# MAGIC ProcedureCode integer,
# MAGIC SRC_InsertedDate date,
# MAGIC SRC_ModifiedDate date,
# MAGIC datasource string,
# MAGIC is_quarantined boolean,
# MAGIC audit_insertdate timestamp,
# MAGIC audit_modifieddate timestamp,
# MAGIC is_current boolean
# MAGIC )
# MAGIC USING DELTA;

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Update old record to implement SCD Type 2
# MAGIC MERGE INTO silver.encounters AS target
# MAGIC USING quality_checks AS source
# MAGIC ON target.EncounterID = source.EncounterID AND target.is_current = true
# MAGIC WHEN MATCHED AND (
# MAGIC     target.SRC_EncounterID != source.SRC_EncounterID OR
# MAGIC     target.PatientID != source.PatientID OR
# MAGIC     target.EncounterDate != source.EncounterDate OR
# MAGIC     target.EncounterType != source.EncounterType OR
# MAGIC     target.ProviderID != source.ProviderID OR
# MAGIC     target.DepartmentID != source.DepartmentID OR
# MAGIC     target.ProcedureCode != source.ProcedureCode OR
# MAGIC     target.SRC_InsertedDate != source.SRC_InsertedDate OR
# MAGIC     target.SRC_ModifiedDate != source.SRC_ModifiedDate OR
# MAGIC     target.datasource != source.datasource OR
# MAGIC     target.is_quarantined != source.is_quarantined
# MAGIC ) THEN
# MAGIC   UPDATE SET
# MAGIC     target.is_current = false,
# MAGIC     target.audit_modifieddate = current_timestamp()
# MAGIC

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Insert new record to implement SCD Type 2
# MAGIC MERGE INTO silver.encounters AS target USING quality_checks AS source ON target.EncounterID = source.EncounterID
# MAGIC AND target.is_current = true
# MAGIC WHEN NOT MATCHED THEN
# MAGIC INSERT
# MAGIC   (
# MAGIC     EncounterID,
# MAGIC     SRC_EncounterID,
# MAGIC     PatientID,
# MAGIC     EncounterDate,
# MAGIC     EncounterType,
# MAGIC     ProviderID,
# MAGIC     DepartmentID,
# MAGIC     ProcedureCode,
# MAGIC     SRC_InsertedDate,
# MAGIC     SRC_ModifiedDate,
# MAGIC     datasource,
# MAGIC     is_quarantined,
# MAGIC     audit_insertdate,
# MAGIC     audit_modifieddate,
# MAGIC     is_current
# MAGIC   )
# MAGIC VALUES
# MAGIC   (
# MAGIC     source.EncounterID,
# MAGIC     source.SRC_EncounterID,
# MAGIC     source.PatientID,
# MAGIC     source.EncounterDate,
# MAGIC     source.EncounterType,
# MAGIC     source.ProviderID,
# MAGIC     source.DepartmentID,
# MAGIC     source.ProcedureCode,
# MAGIC     source.SRC_InsertedDate,
# MAGIC     source.SRC_ModifiedDate,
# MAGIC     source.datasource,
# MAGIC     source.is_quarantined,
# MAGIC     current_timestamp(),
# MAGIC     current_timestamp(),
# MAGIC     true
# MAGIC   );

# COMMAND ----------

# MAGIC %sql
# MAGIC select SRC_EncounterID,datasource,count(patientid) from  silver.encounters
# MAGIC group by all
# MAGIC order by 3 desc
