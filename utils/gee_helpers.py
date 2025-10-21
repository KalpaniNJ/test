# Placeholder for gee_helpers.py
import ee
import geemap
import streamlit as st
import pandas as pd
from datetime import datetime
from utils.config import load_assets


def get_time_series(aoi, start_date, end_date):

    assets = load_assets()
    points = assets["points"]

    startDate = ee.Date(str(start_date))
    endDate = ee.Date(str(end_date))

    # Creates a list of dekads (12-day periods per month) from the given date range
    # Calculates the number of months between startDate and endDate
    # Creates a list of months starting from startDate
    numMonths = endDate.difference(startDate, 'month').round()

    def func_ocb(month):
        return startDate.advance(ee.Number(month), 'month')

    monthSequence = ee.List.sequence(0, numMonths, 1).map(func_ocb)

    # Function to generate dekad dates for a given month

    def func_jha(date):
        date = ee.Date(date)
        y = date.get('year')
        m = date.get('month')

        dekad1 = ee.Date.fromYMD(y, m, 1)
        dekad2 = ee.Date.fromYMD(y, m, 13)
        dekad3 = ee.Date.fromYMD(y, m, 25)

        return [dekad1, dekad2, dekad3]

    generateDekads = func_jha

    # Get the dekadList
    dekadList = monthSequence.map(generateDekads).flatten()

    def func_kbb(date):
        return ee.Algorithms.If(
        ee.Date(date).millis().lte(endDate.millis()),
        date,
        None
        )

    filteredDekadList = dekadList.map(func_kbb).removeAll([None])

    # Remove duplicate dekad dates from filteredDekadList
    filteredDekadList = filteredDekadList.distinct()

    # Define the Lee filter function for GEE
    def lee_filter_gee(img, n=2, ENL=5.0):
        """
        Lee Filter for speckle reduction in GEE.
        """
        img = ee.Image(img)
        kernel = ee.Kernel.square(radius=n, units='pixels', normalize=True)

        # Local mean and variance
        mean_img = img.reduceNeighborhood(reducer=ee.Reducer.mean(), kernel=kernel)
        var_img = img.reduceNeighborhood(reducer=ee.Reducer.variance(), kernel=kernel)

        sigma_v = ee.Number(1.0).divide(ENL).sqrt()  # (1/ENL)^0.5
        sigma_v2 = sigma_v.pow(2)

        var_x = var_img.subtract(mean_img.pow(2).multiply(sigma_v2)) \
                    .divide(ee.Number(1).add(sigma_v2))
        k = var_x.divide(var_img)
        k = k.where(k.lt(0), 0)

        lee_img = mean_img.add(k.multiply(img.subtract(mean_img)))

        # Explicitly ensure output is an ee.Image
        return ee.Image(lee_img).copyProperties(img, img.propertyNames())

    # Define polarization
    polarization = 'VH'

    # Load the Sentinel-1 GRD ImageCollection with raw SAR images (VV, VH)
    s1 = ee.ImageCollection('COPERNICUS/S1_GRD_FLOAT') \
        .filterBounds(aoi) \
        .filterDate(startDate, endDate) \
        .filter(ee.Filter.eq('instrumentMode','IW')) \
        .filter(ee.Filter.listContains('transmitterReceiverPolarisation', polarization)) \
        .filter(ee.Filter.eq('resolution_meters', 10))

    # Apply Lee filter to raw bands
    def filter_raw(img):
        img = ee.Image(img)
        vv_f = ee.Image(lee_filter_gee(img.select('VV'), n=2, ENL=4.0)).rename('VV_filtered')
        vh_f = ee.Image(lee_filter_gee(img.select('VH'), n=2, ENL=4.0)).rename('VH_filtered')
        return img.addBands([vv_f, vh_f])

    s1_filtered = s1.map(filter_raw)

    # Calculate mRVI from filtered bands
    def add_mrvi(img):
        vv = img.select('VV_filtered')
        vh = img.select('VH_filtered')
        mRVI = vv.divide(vv.add(vh)).pow(0.5).multiply(vh.multiply(4).divide(vv.add(vh))).rename('mRVI')
        return img.addBands(mRVI)

    rvi_filtered = s1_filtered.map(add_mrvi).select('mRVI')
    rvi_sorted = rvi_filtered.sort("system:time_start")

    def func_wxd(dekad):
        start_date = ee.Date(dekad)
        currentIndex = ee.Number(filteredDekadList.indexOf(dekad))
        nextIndex = currentIndex.add(1)
        nextDate = ee.Algorithms.If(
            nextIndex.lt(filteredDekadList.size()),
            ee.Date(filteredDekadList.get(nextIndex)),
            endDate
        )

        dekadImages = rvi_sorted.filterDate(start_date, nextDate)
        mRVIImages = dekadImages.select('mRVI')

        def make_image():
            img = mRVIImages.reduce(ee.Reducer.median())
            # Set dekad and system:time_start correctly
            return img.set({
                'dekad': dekad,
                'system:time_start': start_date.millis()
            })

        return ee.Algorithms.If(
            mRVIImages.size().gt(0),
            make_image(),
            None
        )

    createMosaic = func_wxd

    # Convert List to ImageCollection & Remove Nulls
    mosaicImages = ee.List(filteredDekadList.map(createMosaic)).removeAll([None])
    mosaicCollection = ee.ImageCollection.fromImages(mosaicImages)

    def func_zty(img):
        # preserve properties
        img2 = img.multiply(10000).toUint16()
        return img2.copyProperties(img, ['dekad', 'system:time_start'])

    mosaicCollectionUInt16 = mosaicCollection.map(func_zty)

    #................................................Line Graph................................................#
    def sample_image(image, fc):
            fc = ee.FeatureCollection(fc)
            samples = image.sampleRegions(collection=points, scale=10, geometries=True)
            samples = samples.map(lambda f: f.set('time', ee.Date(image.get('system:time_start')).format('YYYY-MM-dd')))
            return fc.merge(samples)

    initial_fc = ee.FeatureCollection([])
    sampled_fc = ee.FeatureCollection(mosaicCollectionUInt16.iterate(sample_image, initial_fc))

    info1 = sampled_fc.getInfo()
    rows1 = [{
        "time": f["properties"].get("time"),
        "mRVI": f["properties"].get("mRVI_median"),
        "point_id": f["properties"].get("system:index")
    } for f in info1["features"]]
    df_line = pd.DataFrame(rows1)
    df_line["time"] = pd.to_datetime(df_line["time"])
    df_line = df_line.sort_values("time")

    #................................................Point Graph................................................#
    def sample_image_points(image):
        return image.sampleRegions(collection=points, scale=10, geometries=True)\
            .map(lambda f: f.set('time', image.date().format('YYYY-MM-dd')))

    sampled_fc2 = mosaicCollectionUInt16.map(sample_image_points).flatten()
    info2 = sampled_fc2.getInfo()
    rows2 = [{
        "time": f["properties"].get("time"),
        "mRVI_median": f["properties"].get("mRVI_median"),
        "point_id": f.get("id")
    } for f in info2["features"]]
    df_points = pd.DataFrame(rows2).dropna()
    df_points["time"] = pd.to_datetime(df_points["time"])
    df_points = df_points.sort_values("time")

    return df_line, df_points


def get_mosaic_collection(aoi, start_date, end_date):

    startDate = ee.Date(str(start_date))
    endDate = ee.Date(str(end_date))

    # Creates a list of dekads (12-day periods per month) from the given date range
    # Calculates the number of months between startDate and endDate
    # Creates a list of months starting from startDate
    numMonths = endDate.difference(startDate, 'month').round()

    def func_ocb(month):
        return startDate.advance(ee.Number(month), 'month')

    monthSequence = ee.List.sequence(0, numMonths, 1).map(func_ocb)

    # Function to generate dekad dates for a given month

    def func_jha(date):
        date = ee.Date(date)
        y = date.get('year')
        m = date.get('month')

        dekad1 = ee.Date.fromYMD(y, m, 1)
        dekad2 = ee.Date.fromYMD(y, m, 13)
        dekad3 = ee.Date.fromYMD(y, m, 25)

        return [dekad1, dekad2, dekad3]

    generateDekads = func_jha

    # Get the dekadList
    dekadList = monthSequence.map(generateDekads).flatten()

    def func_kbb(date):
        return ee.Algorithms.If(
        ee.Date(date).millis().lte(endDate.millis()),
        date,
        None
        )

    filteredDekadList = dekadList.map(func_kbb).removeAll([None])

    # Remove duplicate dekad dates from filteredDekadList
    filteredDekadList = filteredDekadList.distinct()

    # Define the Lee filter function for GEE
    def lee_filter_gee(img, n=2, ENL=5.0):
        """
        Lee Filter for speckle reduction in GEE.
        """
        img = ee.Image(img)
        kernel = ee.Kernel.square(radius=n, units='pixels', normalize=True)

        # Local mean and variance
        mean_img = img.reduceNeighborhood(reducer=ee.Reducer.mean(), kernel=kernel)
        var_img = img.reduceNeighborhood(reducer=ee.Reducer.variance(), kernel=kernel)

        sigma_v = ee.Number(1.0).divide(ENL).sqrt()  # (1/ENL)^0.5
        sigma_v2 = sigma_v.pow(2)

        var_x = var_img.subtract(mean_img.pow(2).multiply(sigma_v2)) \
                    .divide(ee.Number(1).add(sigma_v2))
        k = var_x.divide(var_img)
        k = k.where(k.lt(0), 0)

        lee_img = mean_img.add(k.multiply(img.subtract(mean_img)))

        # Explicitly ensure output is an ee.Image
        return ee.Image(lee_img).copyProperties(img, img.propertyNames())

    # Define polarization
    polarization = 'VH'

    # Load the Sentinel-1 GRD ImageCollection with raw SAR images (VV, VH)
    s1 = ee.ImageCollection('COPERNICUS/S1_GRD_FLOAT') \
        .filterBounds(aoi) \
        .filterDate(startDate, endDate) \
        .filter(ee.Filter.eq('instrumentMode','IW')) \
        .filter(ee.Filter.listContains('transmitterReceiverPolarisation', polarization)) \
        .filter(ee.Filter.eq('resolution_meters', 10))

    # Apply Lee filter to raw bands
    def filter_raw(img):
        img = ee.Image(img)
        vv_f = ee.Image(lee_filter_gee(img.select('VV'), n=2, ENL=4.0)).rename('VV_filtered')
        vh_f = ee.Image(lee_filter_gee(img.select('VH'), n=2, ENL=4.0)).rename('VH_filtered')
        return img.addBands([vv_f, vh_f])

    s1_filtered = s1.map(filter_raw)

    # Calculate mRVI from filtered bands
    def add_mrvi(img):
        vv = img.select('VV_filtered')
        vh = img.select('VH_filtered')
        mRVI = vv.divide(vv.add(vh)).pow(0.5).multiply(vh.multiply(4).divide(vv.add(vh))).rename('mRVI')
        return img.addBands(mRVI)

    rvi_filtered = s1_filtered.map(add_mrvi).select('mRVI')
    rvi_sorted = rvi_filtered.sort("system:time_start")

    def func_wxd(dekad):
        start_date = ee.Date(dekad)
        currentIndex = ee.Number(filteredDekadList.indexOf(dekad))
        nextIndex = currentIndex.add(1)
        nextDate = ee.Algorithms.If(
            nextIndex.lt(filteredDekadList.size()),
            ee.Date(filteredDekadList.get(nextIndex)),
            endDate
        )

        dekadImages = rvi_sorted.filterDate(start_date, nextDate)
        mRVIImages = dekadImages.select('mRVI')

        def make_image():
            img = mRVIImages.reduce(ee.Reducer.median())
            # Set dekad and system:time_start correctly
            return img.set({
                'dekad': dekad,
                'system:time_start': start_date.millis()
            })

        return ee.Algorithms.If(
            mRVIImages.size().gt(0),
            make_image(),
            None
        )

    createMosaic = func_wxd

    # Convert List to ImageCollection & Remove Nulls
    mosaicImages = ee.List(filteredDekadList.map(createMosaic)).removeAll([None])
    mosaicCollection = ee.ImageCollection.fromImages(mosaicImages)

    def func_zty(img):
        # preserve properties
        img2 = img.multiply(10000).toUint16()
        return img2.copyProperties(img, ['dekad', 'system:time_start'])

    mosaicCollectionUInt16 = mosaicCollection.map(func_zty)

    return mosaicCollectionUInt16, filteredDekadList


def compute_statistics(aoi, maskedPaddyClassification, maskedStartMonth, maskedStartMonthDay):

    total_area = (
        maskedPaddyClassification.multiply(ee.Image.pixelArea())
        .reduceRegion(
            reducer=ee.Reducer.sum(),
            geometry=aoi,
            scale=10,
            maxPixels=1e13
        )
        .getInfo()
    )
    total_area_ha = list(total_area.values())[0] / 10000  # convert m² → ha

    # --- Area by Month
    month_area = (
        ee.Image.pixelArea().addBands(maskedStartMonth)
        .reduceRegion(
            reducer=ee.Reducer.sum().group(groupField=1, groupName='month'),
            geometry=aoi,
            scale=10,
            maxPixels=1e13
        )
        .getInfo()
    )
    month_stats = {g["month"]: g["sum"] / 10000 for g in month_area["groups"]}

    # --- Area by MMDD
    mmdd_area = (
        ee.Image.pixelArea().addBands(maskedStartMonthDay)
        .reduceRegion(
            reducer=ee.Reducer.sum().group(groupField=1, groupName='mmdd'),
            geometry=aoi,
            scale=10,
            maxPixels=1e13
        )
        .getInfo()
    )
    mmdd_stats = {g["mmdd"]: g["sum"] / 10000 for g in mmdd_area["groups"]}

    return total_area_ha, month_stats, mmdd_stats


def perform_monitoring(params):
    """Placeholder for seasonal monitoring analysis"""
    return {"trend": []}
