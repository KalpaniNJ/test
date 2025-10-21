# Placeholder for rice_algorithms.py
import ee
import streamlit as st
import pandas as pd
from utils.config import load_assets

def detect_outliers(df_points, dates):
    df_points["time"] = pd.to_datetime(df_points["time"])

    start_date = pd.to_datetime(dates["start"])
    peak_date = pd.to_datetime(dates["peak"])
    harvest_date = pd.to_datetime(dates["harvest"])

    # Subset values
    start_values = df_points[df_points["time"] == start_date]["mRVI_median"]
    peak_values = df_points[df_points["time"] == peak_date]["mRVI_median"]
    harvest_values = df_points[df_points["time"] == harvest_date]["mRVI_median"]

    # Quartiles
    q3_start = start_values.quantile(0.75)
    q1_peak = peak_values.quantile(0.25)

    # Mean values
    mean_start = start_values.mean()
    mean_peak = peak_values.mean()
    mean_harvest = harvest_values.mean()

    # Differences
    diff_start_peak = mean_peak - mean_start
    diff_peak_harvest = mean_peak - mean_harvest

    results = {
        "q3_start": q3_start,
        "q1_peak": q1_peak,
        "mean_start": mean_start,
        "mean_peak": mean_peak,
        "mean_harvest": mean_harvest,
        "diff_start_peak": diff_start_peak,
        "diff_peak_harvest": diff_peak_harvest
    }

    return results

def perform_rice_mapping(aoi, mosaicCollectionUInt16, filteredDekadList, outlier_params, dates):
    """Perform rice mapping using mRVI temporal logic."""

    assets = load_assets()
    roads = assets["roads"]
    water = assets["water"]

    # Extract outlier parameters from the dictionary
    diff_start_peak = outlier_params["diff_start_peak"]
    diff_peak_harvest = outlier_params["diff_peak_harvest"]
    q3_start = outlier_params["q3_start"]
    q1_peak = outlier_params["q1_peak"]

    # Earth Engine dates
    sosDate = ee.Date(dates['start'])
    peakDate = ee.Date(dates['peak'])
    fallDate = ee.Date(dates['harvest'])

    # ---------------- mRVI SOS-Peak-Fall analysis ----------------
    #  Function to get adjacent dekads
    def getAdjacentDekads(targetDate, dekadList):
        index = dekadList.indexOf(targetDate)
        return ee.List([
            dekadList.get(ee.Number(index).subtract(1)),
            targetDate,
            dekadList.get(ee.Number(index).add(1))
        ]).filter(ee.Filter.neq('item', None))

    # Extract SOS, Peak, Fall Images
    sosWindow = getAdjacentDekads(sosDate, filteredDekadList)
    sosImages = mosaicCollectionUInt16.filter(ee.Filter.inList('dekad', sosWindow))
    sosMin = sosImages.reduce(ee.Reducer.min())

    peakWindow = getAdjacentDekads(peakDate, filteredDekadList)
    peakImages = mosaicCollectionUInt16.filter(ee.Filter.inList('dekad', peakWindow))
    peakMax = peakImages.reduce(ee.Reducer.max())

    fallWindow = getAdjacentDekads(fallDate, filteredDekadList)
    fallImages = mosaicCollectionUInt16.filter(ee.Filter.inList('dekad', fallWindow))
    fallMin = fallImages.reduce(ee.Reducer.min())

    # Main Conditions
    positiveGrowth = peakMax.subtract(sosMin).gt(diff_start_peak/2)
    negativeDecline = peakMax.subtract(fallMin).gt(diff_peak_harvest/2)

    # Additional Temporal and Quartile Checks
    # thresholds from quartile analysis
    sosMaxThreshold = q3_start
    peakMinThreshold = q1_peak

    # Check SOS < Q3 and Peak > Q1
    valuePatternMask = sosMin.lte(sosMaxThreshold).And(peakMax.gte(peakMinThreshold))

    # Time difference in months between SOS min and Peak max
    timeDiffMonths = peakDate.difference(sosDate, 'month')
    timePatternMask = timeDiffMonths.gte(1)

    # Combine All Conditions
    paddyMask = positiveGrowth.And(negativeDecline).And(valuePatternMask).And(timePatternMask)

    paddyClassification = paddyMask.clip(aoi).rename('paddy_classified').selfMask()

    def clean_paddy_mask(paddy_mask, aoi, kernel_radius=1, min_object_area=10000):
        """Clean a paddy mask by masking tree cover and built-up areas, applying dilation, and removing small objects."""
        # Load ESA WorldCover and clip
        esa = ee.ImageCollection('ESA/WorldCover/v200').first().clip(aoi)
        
        # Mask tree cover and built-up areas
        tree_cover = esa.eq(10)
        built_up = esa.eq(50)
        paddy_clean = paddy_mask.updateMask(tree_cover.Not()).updateMask(built_up.Not())
        
        # Apply dilation
        kernel = ee.Kernel.circle(radius=kernel_radius, units='pixels')
        paddy_clean = paddy_clean.focal_max(kernel=kernel, iterations=1)
        
        # Object-based noise removal
        object_size = paddy_clean.connectedPixelCount(maxSize=128, eightConnected=False)
        pixel_area = ee.Image.pixelArea()
        object_area = object_size.multiply(pixel_area)
        
        # Mask small objects
        paddy_clean = paddy_clean.updateMask(object_area.gte(min_object_area))
        
        return paddy_clean

    # Add generalization
    cleaned_paddy = clean_paddy_mask(paddyClassification, aoi)

    # ---------------- Mask roads & water features ----------------
    # Set a mask property for each feature
    water = water.map(lambda f: f.set('mask', 1))
    roads = roads.map(lambda f: f.set('mask', 1))

    # Optional: buffer roads (e.g., 3 meters)
    roadsBuffer = roads.map(lambda f: f.buffer(3))

    # Convert features to raster mask
    waterMask = water.reduceToImage(properties=['mask'], reducer=ee.Reducer.first()).clip(aoi).unmask(0).gt(0)
    roadsMask = roadsBuffer.reduceToImage(properties=['mask'], reducer=ee.Reducer.first()).clip(aoi).unmask(0).gt(0)

    # Combine masks
    eraseMask = waterMask.Or(roadsMask)

    # Apply mask to paddyClassification
    maskedPaddyClassification = cleaned_paddy.updateMask(eraseMask.Not()).rename('masked_paddy_classified')
    maskedPaddyClassification = maskedPaddyClassification.updateMask(maskedPaddyClassification.gt(0))

    # ---------------- Get differences ----------------
    def calculateDifference(prevImage, nextImage):
        diff = nextImage.subtract(prevImage)
        return diff.set({
            'dekad1': prevImage.get('system:index'),
            'dekad2': nextImage.get('system:index'),
            'system:time_start': nextImage.get('system:time_start'),
            'dekad1_time': prevImage.get('system:time_start'),
            'dekad2_time': nextImage.get('system:time_start')
        })

    # Create list of consecutive image pairs
    mosaicList = mosaicCollectionUInt16.toList(mosaicCollectionUInt16.size())

    def func_ycf(i):
        prev = ee.Image(mosaicList.get(ee.Number(i).subtract(1)))
        next = ee.Image(mosaicList.get(i))
        return calculateDifference(prev, next)

    differences = ee.ImageCollection(
        ee.List.sequence(1, mosaicList.size().subtract(1)).map(func_ycf)
    )

    # ---------------- Check the continuation of positive differences ----------------
    def findSequentialGrowth(differences):
        diffList = differences.toList(differences.size())
        size = differences.size()

        def func_yth(index):
            currImg = ee.Image(diffList.get(index))
            nextIndex = ee.Number(index).add(1)
            hasNext = nextIndex.lt(size)
            nextImg = ee.Image(ee.Algorithms.If(hasNext, diffList.get(nextIndex), ee.Image(0)))

            seqGrowth = currImg.gt(0).rename('sequential_growth') \
                .set('start_dekad', currImg.get('dekad1')) \
                .set('end_dekad', ee.Algorithms.If(hasNext, nextImg.get('dekad2'), currImg.get('dekad2'))) \
                .set('system:time_start', currImg.get('system:time_start')) \
                .set('start_time', currImg.get('dekad1_time')) \
                .set('end_time', ee.Algorithms.If(hasNext, nextImg.get('dekad2_time'), currImg.get('dekad2_time')))

            isContinuous = ee.Image(ee.Algorithms.If(
                hasNext,
                currImg.gt(0).And(nextImg.gt(0)),
                ee.Image(0)
            ))

            return seqGrowth.addBands(isContinuous.rename('is_continuous')).set('growth_period', index)

        # Map over all indices and create ImageCollection
        images = ee.List.sequence(0, size.subtract(2)).map(func_yth)
        return ee.ImageCollection.fromImages(images)

    # Create sequential growth map
    sequentialDiffs = findSequentialGrowth(differences)

    def func_wun(img):
        return img.select('sequential_growth') \
            .multiply(img.select('is_continuous')) \
            .rename('sequential_growth') \
            .round() \
            .set('growth_period', img.get('growth_period')) \
            .set('start_time', ee.Number(img.get('start_time'))) \
            .set('end_time', ee.Number(img.get('end_time')))

    sequentialImgs = sequentialDiffs.map(func_wun)

    imgList = sequentialImgs.toList(sequentialImgs.size())

    # ---------------- Track start date of the longest streak ----------------
    # Initial dictionary for iterate
    init = ee.Dictionary({
        'currentLength': ee.Image(0),
        'longestLength': ee.Image(0),
        'currentStartDate': ee.Image(0),
        'longestStartDate': ee.Image(0)
    })

    def func_hxg(imgObj, prev):
        img = ee.Image(imgObj).clip(aoi)
        prev = ee.Dictionary(prev)

        prevCurrentLength = ee.Image(prev.get('currentLength'))
        prevLongestLength = ee.Image(prev.get('longestLength'))
        prevCurrentStartDate = ee.Image(prev.get('currentStartDate'))
        prevLongestStartDate = ee.Image(prev.get('longestStartDate'))

        prevCurrentStartMonth = ee.Image(prev.get('currentStartMonth'))
        prevLongestStartMonth = ee.Image(prev.get('longestStartMonth'))

        prevCurrentStartMonthDay = ee.Image(prev.get('currentStartMonthDay'))
        prevLongestStartMonthDay = ee.Image(prev.get('longestStartMonthDay'))

        isOne = img.eq(1)

        # Increment current streak if 1, reset if 0
        newCurrentLength = prevCurrentLength.add(isOne).multiply(isOne)

        # --- Start date (millis) ---
        newCurrentStartDate = prevCurrentStartDate.where(
            prevCurrentLength.eq(0).And(isOne),
            ee.Image.constant(ee.Number(img.get('start_time')))
        )

        # --- Start month (MM) ---
        newCurrentStartMonth = prevCurrentStartMonth.where(
            prevCurrentLength.eq(0).And(isOne),
            ee.Image.constant(ee.Date(img.get('start_time')).get('month'))
        )

        # --- Start month-day (MMDD, e.g., March 5 = 305) ---
        newCurrentStartMonthDay = prevCurrentStartMonthDay.where(
            prevCurrentLength.eq(0).And(isOne),
            ee.Image.constant(
                ee.Number(ee.Date(img.get('start_time')).get('month')).multiply(100)
                .add(ee.Number(ee.Date(img.get('start_time')).get('day')))
            )
        )

        # --- Update longest streak length ---
        newLongestLength = prevLongestLength.max(newCurrentLength)

        # --- Update longest streak start date/month/month-day if this is a new max ---
        newLongestStartDate = prevLongestStartDate \
            .where(newCurrentLength.gt(prevLongestLength), newCurrentStartDate) \
            .where(newCurrentLength.eq(prevLongestLength)
                .And(newCurrentStartDate.lt(prevLongestStartDate)),
                newCurrentStartDate)

        newLongestStartMonth = prevLongestStartMonth \
            .where(newCurrentLength.gt(prevLongestLength), newCurrentStartMonth) \
            .where(newCurrentLength.eq(prevLongestLength)
                .And(newCurrentStartDate.lt(prevLongestStartDate)),
                newCurrentStartMonth)

        newLongestStartMonthDay = prevLongestStartMonthDay \
            .where(newCurrentLength.gt(prevLongestLength), newCurrentStartMonthDay) \
            .where(newCurrentLength.eq(prevLongestLength)
                .And(newCurrentStartDate.lt(prevLongestStartDate)),
                newCurrentStartMonthDay)

        return ee.Dictionary({
            'currentLength': newCurrentLength,
            'longestLength': newLongestLength,
            'currentStartDate': newCurrentStartDate,
            'longestStartDate': newLongestStartDate,
            'currentStartMonth': newCurrentStartMonth,
            'longestStartMonth': newLongestStartMonth,
            'currentStartMonthDay': newCurrentStartMonthDay,
            'longestStartMonthDay': newLongestStartMonthDay
        })

    init = ee.Dictionary({
        'currentLength': ee.Image(0),
        'longestLength': ee.Image(0),
        'currentStartDate': ee.Image(0),
        'longestStartDate': ee.Image(0),
        'currentStartMonth': ee.Image(0),
        'longestStartMonth': ee.Image(0),
        'currentStartMonthDay': ee.Image(0),
        'longestStartMonthDay': ee.Image(0)
    })

    # Run iteration
    result = imgList.iterate(func_hxg, init)
    final = ee.Dictionary(result)

    # Final maps
    finalLongest = ee.Image(final.get('longestLength')).clip(aoi).rename('Longest_Streak')
    finalStartDate = ee.Image(final.get('longestStartDate')).clip(aoi).rename('Longest_Streak_Start')
    finalStartMonth = ee.Image(final.get('longestStartMonth')).clip(aoi).rename('Longest_Streak_Start_MM')
    finalStartMonthDay = ee.Image(final.get('longestStartMonthDay')).clip(aoi).rename('Longest_Streak_Start_MMDD')

    # Mask to paddy and remove zeros
    maskedLongest = finalLongest.updateMask(maskedPaddyClassification).updateMask(finalLongest.neq(0))
    maskedStartDate = finalStartDate.updateMask(maskedPaddyClassification).updateMask(finalStartDate.neq(0))
    maskedStartMonth = finalStartMonth.updateMask(maskedPaddyClassification).updateMask(finalStartMonth.neq(0))
    maskedStartMonthDay = finalStartMonthDay.updateMask(maskedPaddyClassification).updateMask(finalStartMonthDay.neq(0))

    # ---------------- Create Growing Season map ----------------
    stats = maskedStartDate.reduceRegion(
        reducer=ee.Reducer.minMax(),
        geometry=aoi,
        scale=10,
        maxPixels=1e9,
        bestEffort=True
    )

    minValue = ee.Number(stats.get('Longest_Streak_Start_min'))
    maxValue = ee.Number(stats.get('Longest_Streak_Start_max'))

    # --- Define thresholds to split into 3 classes ---
    earlySeasonThreshold = minValue.add(maxValue.subtract(minValue).multiply(0.33))
    midSeasonThreshold = minValue.add(maxValue.subtract(minValue).multiply(0.66))

    # --- Classify into 3 growing season classes ---
    growingSeason = maskedStartDate.expression(
        "(b('Longest_Streak_Start') <= early) ? 0" +
        ": (b('Longest_Streak_Start') > early && b('Longest_Streak_Start') <= mid) ? 1" +
        ": 2",
        {
            'early': earlySeasonThreshold,
            'mid': midSeasonThreshold
        }
    ).updateMask(maskedPaddyClassification)

    return maskedPaddyClassification, growingSeason, maskedStartMonth, maskedStartMonthDay
