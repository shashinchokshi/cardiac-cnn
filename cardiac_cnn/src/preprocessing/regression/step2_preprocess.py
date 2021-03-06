__author__ = 'Julian'
import helpers
import settings
import csv
import pandas
from helpers_dicom import *
import scipy
import scipy.misc
import cv2

def create_csv_data():
    print("Creating csv file from dicom data")
    row_no = 0
    with open("dicom_data_test.csv", "w", newline='') as csv_file:
        csv_writer = csv.writer(csv_file, delimiter=";", quoting=csv.QUOTE_MINIMAL)
        csv_writer.writerow(["patient_id", "slice_no", "frame_no", "rows", "columns", "spacing", "slice_thickness", "slice_location", "slice_location2", "plane", "image_position", "sv", "time", "manufact", "modelname", "age", "birth", "sex", "file_name", "angle", "o1", "o2", "o3", "o4", "o5","o6"])
        for dicom_data_test in helpers.enumerate_sax_files():
            row_no += 1
            if row_no % 1000 == 0:
                print(row_no)

            csv_writer.writerow([
                str(dicom_data_test.patient_id),
                str(dicom_data_test.series_number),
                str(dicom_data_test.instance_number),
                str(dicom_data_test.rows),
                str(dicom_data_test.columns),
                str(dicom_data_test.spacing[0]),
                str(dicom_data_test.slice_thickness),
                str(dicom_data_test.slice_location),
                str(dicom_data_test.get_location()),
                dicom_data_test.in_plane_encoding_direction,
                str(dicom_data_test.image_position),
                str(dicom_data_test.get_value("SequenceVariant")),
                str(dicom_data_test.get_value("InstanceCreationTime")),
                str(dicom_data_test.get_value("Manufacturer")),
                str(dicom_data_test.get_value("ManufacturerModelName")),
                str(dicom_data_test.get_value("PatientAge")),
                str(dicom_data_test.get_value("PatientBirthDate")),
                str(dicom_data_test.get_value("PatientSex")),
                dicom_data_test.file_name.replace(".dcm", ""),
                str(dicom_data_test.get_value("FlipAngle")),
                str(round(dicom_data_test.image_orientation_patient[0], 2)),
                str(round(dicom_data_test.image_orientation_patient[1], 2)),
                str(round(dicom_data_test.image_orientation_patient[2], 2)),
                str(round(dicom_data_test.image_orientation_patient[3], 2)),
                str(round(dicom_data_test.image_orientation_patient[4], 2)),
                str(round(dicom_data_test.image_orientation_patient[5], 2))
            ])


def up_down(current_value, previous_value):
    # previous_value = previous_value.fillna(-99999)
    delta = current_value - previous_value
    delta = delta.fillna(0)
    updown = pandas.Series(delta.apply(lambda x: 0 if x == 0 else 1 if x > 0 else -1))
    return updown


def slice_delta(current_value, next_value):
    # previous_value = previous_value.fillna(-99999)
    delta = current_value - next_value
    delta = delta.fillna(999)
    return delta


def count_small_deltas(current_value):
    # previous_value = previous_value.fillna(-99999)
    res = len(current_value[abs(current_value) < 2])
    return res


def get_age_years(age_string):
    res = 0
    if "Y" in age_string:
        age_string = age_string.replace("Y", "")
        res = float(age_string)
    if "M" in age_string:
        age_string = age_string.replace("M", "")
        res = round(float(age_string) / 12., 2)
    if "W" in age_string:
        age_string = age_string.replace("W", "")
        res = round(float(age_string) / 52., 2)
    return res


def enrich_dicom_csvdata():
    print("Enriching dicom csv data with extra columns and stats")
    dicom_data_test = pandas.read_csv("dicom_data_test.csv", sep=";")
    dicom_data_test["age_years"] = dicom_data_test["age"].apply(lambda x: get_age_years(x))
    dicom_data_test["patient_id_frame"] = dicom_data_test["patient_id"].map(str) + "_" + dicom_data_test["frame_no"].map(str)
    dicom_data_test = dicom_data_test.sort_values(["patient_id", "frame_no", "slice_location", "file_name"], ascending=[1, 1, 1, 1])

    # aggrageted updown information < 0 means slice location increased from apex to base and > 0 from base to apex, we want everything from base to apex..
    patient_grouped = dicom_data_test.groupby("patient_id_frame")
    print(patient_grouped.describe())
    dicom_data_test['up_down'] = patient_grouped['time'].apply(lambda x: up_down(x, x.shift(1)))
    dicom_data_test['up_down_agg'] = patient_grouped["up_down"].transform(lambda x: sum(x))
    dicom_data_test['slice_location_sort'] = dicom_data_test['slice_location'] * dicom_data_test['up_down_agg']
    dicom_data_test = dicom_data_test.sort_values(["patient_id", "frame_no", "slice_location_sort", "slice_location", "file_name"])

    # now compute the deltas between slices
    patient_grouped = dicom_data_test.groupby("patient_id_frame")
    dicom_data_test['slice_location_delta'] = patient_grouped['slice_location'].apply(lambda x: slice_delta(x, x.shift(-1)))
    dicom_data_test['small_slice_count'] = patient_grouped['slice_location_delta'].transform(lambda x: count_small_deltas(x))
    dicom_data_test["slice_count"] = patient_grouped["up_down"].transform("count")
    dicom_data_test["normal_slice_count"] = dicom_data_test["slice_count"] - dicom_data_test['small_slice_count']

    # delete all slices with delta '0'
    dicom_data_test = dicom_data_test[dicom_data_test["slice_location_delta"] != 0]

    # again determine updown for some special cases (341)
    patient_grouped = dicom_data_test.groupby("patient_id_frame")
    dicom_data_test['up_down'] = patient_grouped['time'].apply(lambda x: up_down(x, x.shift(1)))
    dicom_data_test['up_down_agg'] = patient_grouped["up_down"].transform(lambda x: sum(x))

    dicom_data_test.to_csv("dicom_data_test_enriched.csv", sep=";")

    dicom_data_test = dicom_data_test[dicom_data_test["frame_no"] == 1]
    dicom_data_test.to_csv("dicom_data_test_enriched_frame1.csv", sep=";")


def enrich_testdata():
    print("Enriching train data with extra columns and stats")
    test_data = pandas.read_csv("test_solution.csv", sep=",")
    dicom_data_test = pandas.read_csv("dicom_data_test_enriched_frame1.csv", sep=";")
    patient_grouped = dicom_data_test.groupby("patient_id")

    enriched_testdata = patient_grouped.first().reset_index()
    enriched_testdata = enriched_testdata[["patient_id", "rows", "columns", "spacing", "slice_thickness", "plane", "slice_count", "up_down_agg", "age_years", "sex", "small_slice_count", "normal_slice_count", "angle"]]
    enriched_testdata = pandas.merge(left=enriched_testdata, right=test_data, how='left', left_on='patient_id', right_on='Id')

    enriched_testdata["pred_dia"] = 0
    enriched_testdata["error_dia"] = 0
    enriched_testdata["abserr_dia"] = 0
    enriched_testdata["pred_sys"] = 0
    enriched_testdata["error_sys"] = 0
    enriched_testdata["abserr_sys"] = 0

    enriched_testdata.to_csv("test_enriched.csv", sep=",", index=False)


def get_patient_id(dir):
    parts = dir.split('/')
    res = parts[len(parts) - 3]
    return res


def get_slice_type(dir_name):
    parts = dir_name.split('/')
    res = parts[len(parts) - 1]
    return res

if __name__ == "__main__":
    create_csv_data()
    enrich_dicom_csvdata()
    enrich_testdata()
    print("Done")
