import streamlit as st
import geemap
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
import seaborn as sns
import ee
from datetime import datetime
import calendar
import numpy as np
from scipy.signal import argrelextrema
import plotly.express as px
import plotly.graph_objects as go
from streamlit_folium import folium_static
import geemap.foliumap as geemap
from utils.config import AOI_OPTIONS, load_assets


def show(params):
    st.title("Seasonal Monitoring")
    if params["run_monitor"]:
        st.spinner("Running seasonal monitoring...")
        with st.spinner(f"Running Analysis for {params['aoi_mnt']} ({params['start_date_mnt']} → {params['end_date_mnt']})"):
        
            # -------------------- Define aoi_mt --------------------
            aoi_path_mt = AOI_OPTIONS[params["aoi_mnt"]]
            aoi_mt = ee.FeatureCollection(aoi_path_mt).geometry()

            # -------------------- Load assets --------------------
            assets = load_assets()
            points = assets["points"]
            water = assets["water"]
            roads = assets["roads"]

            start_date_mt = ee.Date(str(params["start_date_mnt"]))
            end_date_mt = ee.Date(str(params["end_date_mnt"]))

            # Creates a list of dekads (12-day periods per month) from the given date range
            # Calculates the number of months between start_date_mnt and end_date_mnt
            # Creates a list of months starting from start_date_mnt
            numMonths = end_date_mt.difference(start_date_mt, 'month').round()

            def func_ocb(month):
                return start_date_mt.advance(ee.Number(month), 'month')

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
                ee.Date(date).millis().lte(end_date_mt.millis()),
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
                .filterBounds(aoi_mt) \
                .filterDate(start_date_mt, end_date_mt) \
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
                    end_date_mt
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
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.subheader("Time Series Analysis:")
                #................................................Line Graph Visualization................................................#
                # sample each image at all points and add time property
                def sample_image(image, fc):
                    fc = ee.FeatureCollection(fc)
                    
                    samples = image.sampleRegions(collection=points, scale=10, geometries=True)
                    
                    # Add time property as string
                    def add_time(f):
                        return f.set('time', ee.Date(image.get('system:time_start')).format('YYYY-MM-dd'))
                    
                    samples = samples.map(add_time)
                    
                    # Merge with previous features
                    return fc.merge(samples)

                # Iterate over ImageCollection
                initial_fc = ee.FeatureCollection([])
                sampled_fc = ee.FeatureCollection(mosaicCollectionUInt16.iterate(sample_image, initial_fc))

                # Convert to client-side Pandas DataFrame
                sampled_info = sampled_fc.getInfo()
                rows = []
                for f in sampled_info['features']:
                    props = f['properties']
                    rows.append({
                        "time": props.get('time'),
                        "mRVI": props.get('mRVI_median'),
                        "point_id": props.get('system:index')
                    })

                df = pd.DataFrame(rows)
                df['time'] = pd.to_datetime(df['time'])
                df = df.sort_values('time')

                # Plot time series for each point
                plt.figure(figsize=(12,6))
                for pid, group in df.groupby("point_id"):
                    plt.plot(group['time'], group['mRVI'], marker='o', label=f"Point {pid}")

                # Plot overall mean across points
                mean_df = df.groupby('time')['mRVI'].mean().reset_index()
                plt.plot(mean_df['time'], mean_df['mRVI'], color='green', linewidth=2, marker='o', markersize=6, label='Mean mRVI')

                # Format x-axis to show full date (YYYY-MM-DD)
                plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
                plt.gca().xaxis.set_major_locator(mdates.AutoDateLocator())

                plt.xlabel("Date")
                plt.ylabel("mRVI Value")
                plt.title("Time Series of mean mRVI at Sample Points")
                plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=8)
                plt.xticks(rotation=45)  # rotate x-axis labels for readability
                plt.tight_layout()
                st.pyplot(plt.gcf())

            with col2:
                st.subheader(" ")
                #................................................Point Data Visualization................................................#
                # Sample each image at all points and add time property
                def sample_image(image):
                    return image.sampleRegions(
                        collection=points,
                        scale=10,
                        geometries=True
                    ).map(lambda f: f.set('time', image.date().format('YYYY-MM-dd')))

                # Map over the ImageCollection
                sampled_fc = mosaicCollectionUInt16.map(sample_image).flatten()

                # Convert to Pandas DataFrame
                sampled_info = sampled_fc.getInfo()  # now safe
                rows = []
                for f in sampled_info['features']:
                    props = f['properties']
                    rows.append({
                        "time": props.get('time'),
                        "mRVI_median": props.get('mRVI_median'),
                        "point_id": f.get('id')  # Feature ID
                    })

                df = pd.DataFrame(rows)
                df['time'] = pd.to_datetime(df['time'])
                df = df.sort_values('time')

                plt.figure(figsize=(12,6))
                for pid, group in df.groupby("point_id"):
                    plt.plot(group['time'], group['mRVI_median'], marker='o', linestyle='-', markersize=5, alpha=0.7)

                plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
                plt.gca().xaxis.set_major_locator(mdates.AutoDateLocator())
                plt.xticks(rotation=45)

                plt.xlabel("Date")
                plt.ylabel("mRVI Value")
                plt.title("Time Series of mRVI at Sample Points")
                plt.tight_layout()
                st.pyplot(plt.gcf())

            with col3:
                st.subheader("Outlier Analysis:")
                # ---------------------- Plot Boxplot ---------------------- #
                # Reshape data (long format) for boxplot
                df_long = df.melt(
                    id_vars=["time"],                # Keep time as identifier
                    value_vars=["mRVI_median"],      # The values to plot
                    var_name="variable",
                    value_name="value"
                )

                # Add point identifier as a category (so seaborn can distinguish points)
                df_long['point'] = df['point_id']

                # Plot boxplot
                plt.figure(figsize=(12,6))
                sns.boxplot(x="time", y="value", data=df_long)
                plt.xticks(rotation=45)
                plt.xlabel("Date")
                plt.ylabel("mRVI Value")
                plt.title("mRVI Dispersion and Outlier Analysis at Sample Points")
                st.pyplot(plt.gcf())

            # Compute median mRVI across points
            median_df = df.groupby('time')['mRVI_median'].median().reset_index()
            mRVI_values = median_df['mRVI_median'].values
            time_values = median_df['time'].values

            # ------------------ Start Date ------------------ #
            prv_fall_date = pd.to_datetime(time_values[0])  # first available date

            # ------------------ SOS Date ------------------ #
            # Detect local minima in mRVI
            local_min_idx = argrelextrema(mRVI_values, np.less, order=1)[0]

            # Pick the first local minimum after the start
            next_sos_idx = local_min_idx[local_min_idx > 0][0] if len(local_min_idx) > 0 else 0
            next_sos_date = pd.to_datetime(time_values[next_sos_idx])

            # ------------------ Next Peak Date ------------------ #
            next_peak_date = pd.to_datetime(time_values[-1])  # last available date

            # Convert time to datetime
            df_long['time'] = pd.to_datetime(df_long['time'])

            # Use the detected dates
            start_date = prv_fall_date
            sos_date = next_sos_date
            peak_date = next_peak_date

            # ---------------------- Quantile Calculation ---------------------- #
            start_values = df_long[df_long['time'] == start_date]['value']
            sos_values = df_long[df_long['time'] == sos_date]['value']
            peak_values = df_long[df_long['time'] == peak_date]['value']

            # Calculate quartiles
            q3_sos = sos_values.quantile(0.75)
            q1_peak = peak_values.quantile(0.25)

            # ---------------------- Difference Calculation ---------------------- #
            mean_start = start_values.mean()
            mean_sos = sos_values.mean()
            mean_peak = peak_values.mean()

            diff_start_sos = mean_start - mean_sos
            diff_sos_peak = mean_peak - mean_sos

            #..........................................................mRVI SOS-Peak-Fall analysis..........................................................#
            #  Function to get adjacent dekads
            def getAdjacentDekads(targetDate, dekadList):
                index = dekadList.indexOf(targetDate)
                return ee.List([
                    dekadList.get(ee.Number(index).subtract(1)),
                    targetDate,
                    dekadList.get(ee.Number(index).add(1))
                ]).filter(ee.Filter.neq('item', None))

            # Extract SOS, Peak, Fall Images
            start_Window = getAdjacentDekads(start_date, filteredDekadList)
            start_Images = mosaicCollectionUInt16.filter(ee.Filter.inList('dekad', start_Window))
            start_Max = start_Images.reduce(ee.Reducer.max())

            sos_Window = getAdjacentDekads(sos_date, filteredDekadList)
            sos_Images = mosaicCollectionUInt16.filter(ee.Filter.inList('dekad', sos_Window))
            sos_Min = sos_Images.reduce(ee.Reducer.min())

            peak_Window = getAdjacentDekads(peak_date, filteredDekadList)
            peak_Images = mosaicCollectionUInt16.filter(ee.Filter.inList('dekad', peak_Window))
            peak_Max = peak_Images.reduce(ee.Reducer.max())

            # Main Conditions
            positive_Growth = peak_Max.subtract(sos_Min).gt(diff_sos_peak/2)
            negative_Decline = start_Max.subtract(sos_Min).gt(diff_start_sos/2)

            # Additional Temporal and Quartile Checks
            # thresholds from quartile analysis
            sos_MaxThreshold = q3_sos
            peak_MinThreshold = q1_peak

            # Check SOS < Q3 and Peak > Q1
            value_PatternMask = sos_Min.lte(sos_MaxThreshold).And(peak_Max.gte(peak_MinThreshold))

            # Combine All Conditions
            paddyMask = positive_Growth.And(negative_Decline).And(value_PatternMask)

            paddyClassification = paddyMask.clip(aoi_mt).rename('paddy_classified').selfMask()

            def clean_paddy_mask(paddy_mask, aoi_mt, kernel_radius=1, min_object_area=10000):
                """Clean a paddy mask by masking tree cover and built-up areas, applying dilation, and removing small objects."""
                # Load ESA WorldCover and clip
                esa = ee.ImageCollection('ESA/WorldCover/v200').first().clip(aoi_mt)
                
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
            cleaned_paddy = clean_paddy_mask(paddyClassification, aoi_mt)

            #....................................................Mask roads & water features....................................................#
            # Set a mask property for each feature
            water = water.map(lambda f: f.set('mask', 1))
            roads = roads.map(lambda f: f.set('mask', 1))

            # Optional: buffer roads (e.g., 3 meters)
            roadsBuffer = roads.map(lambda f: f.buffer(3))

            # Convert features to raster mask
            waterMask = water.reduceToImage(properties=['mask'], reducer=ee.Reducer.first()).clip(aoi_mt).unmask(0).gt(0)
            roadsMask = roadsBuffer.reduceToImage(properties=['mask'], reducer=ee.Reducer.first()).clip(aoi_mt).unmask(0).gt(0)

            # Combine masks
            eraseMask = waterMask.Or(roadsMask)

            # Apply mask to paddyClassification
            maskedPaddyClassification = cleaned_paddy.updateMask(eraseMask.Not()).rename('masked_paddy_classified')
            maskedPaddyClassification = maskedPaddyClassification.updateMask(maskedPaddyClassification.gt(0))

            #...........................................................Get differences............................................................#
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

            #..........................................................Check the continuation of positive differences..........................................................#
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

            #..........................................................Track start date of the longest streak..........................................................#
            # Initial dictionary for iterate
            init = ee.Dictionary({
                'currentLength': ee.Image(0),
                'longestLength': ee.Image(0),
                'currentStartDate': ee.Image(0),
                'longestStartDate': ee.Image(0)
            })

            def func_hxg(imgObj, prev):
                img = ee.Image(imgObj).clip(aoi_mt)
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
            finalLongest = ee.Image(final.get('longestLength')).clip(aoi_mt).rename('Longest_Streak')
            finalStartDate = ee.Image(final.get('longestStartDate')).clip(aoi_mt).rename('Longest_Streak_Start')
            finalStartMonth = ee.Image(final.get('longestStartMonth')).clip(aoi_mt).rename('Longest_Streak_Start_MM')
            finalStartMonthDay = ee.Image(final.get('longestStartMonthDay')).clip(aoi_mt).rename('Longest_Streak_Start_MMDD')

            # Mask to paddy and remove zeros
            maskedLongest = finalLongest.updateMask(maskedPaddyClassification).updateMask(finalLongest.neq(0))
            maskedStartDate = finalStartDate.updateMask(maskedPaddyClassification).updateMask(finalStartDate.neq(0))
            maskedStartMonth = finalStartMonth.updateMask(maskedPaddyClassification).updateMask(finalStartMonth.neq(0))
            maskedStartMonthDay = finalStartMonthDay.updateMask(maskedPaddyClassification).updateMask(finalStartMonthDay.neq(0))

            st.subheader("Paddy Maps:")
            aoi_centroid_mt = aoi_mt.centroid().coordinates().getInfo()
            Map_SM = geemap.Map(center=[aoi_centroid_mt[1], aoi_centroid_mt[0]], zoom=12)
            Map_SM.add_basemap("SATELLITE")

            Map_SM.addLayer(maskedPaddyClassification,
                        {"min": 0, "max": 1, "palette": ['red', 'green']},
                        "Paddy Map")
            Map_SM.addLayer(maskedStartMonth,
                        {"min": 1, "max": 12, "palette": ["blue", "cyan", "green", "lime", "yellow", "orange", "red", "pink", "purple", "brown", "gray", "black"]},
                        "Start Month", False)
            Map_SM.addLayer(maskedStartMonthDay,
                        {"min": 101, "max": 1231, "palette": ["blue", "cyan", "green", "yellow", "orange", "brown"]},
                        "Start Month–Day", False)

            Map_SM.addLayerControl()
            Map_SM.to_streamlit()


            st.subheader("Paddy Area Statistics:")
            # Total area (all paddy pixels)
            total_area = maskedPaddyClassification.multiply(ee.Image.pixelArea()) \
                .reduceRegion(
                    reducer=ee.Reducer.sum(),
                    geometry=aoi_mt,
                    scale=10,
                    maxPixels=1e13
                ).getInfo()["masked_paddy_classified"] / 10000   # m² → ha
            st.success(f"🌾 Total Paddy Extent: {total_area:,.2f} ha")

            # Area By Month
            month_area = ee.Image.pixelArea().addBands(maskedStartMonth) \
                .reduceRegion(
                    reducer=ee.Reducer.sum().group(
                        groupField=1,
                        groupName='month'
                    ),
                    geometry=aoi_mt,
                    scale=10,
                    maxPixels=1e13
                ).getInfo()

            # Convert to hectares
            month_groups = month_area["groups"]
            month_stats = {g["month"]: g["sum"] / 10000 for g in month_groups}

            # Area By MMDD
            mmdd_area = ee.Image.pixelArea().addBands(maskedStartMonthDay) \
                .reduceRegion(
                    reducer=ee.Reducer.sum().group(
                        groupField=1,
                        groupName='mmdd'
                    ),
                    geometry=aoi_mt,
                    scale=10,
                    maxPixels=1e13
                ).getInfo()

            # Convert to hectares
            mmdd_groups = mmdd_area["groups"]
            mmdd_stats = {g["mmdd"]: g["sum"] / 10000 for g in mmdd_groups}

            # SEASONAL STATISTICS & VISUALIZATION
            season_start = 10
            seasonal_order = [(season_start + i - 1) % 12 + 1 for i in range(12)]

            # Handle potential empty stats safely
            month_groups = month_area.get("groups", [])
            month_stats = {int(g["month"]): g["sum"] / 10000 for g in month_groups if "month" in g}

            mmdd_groups = mmdd_area.get("groups", [])
            mmdd_stats = {int(g["mmdd"]): g["sum"] / 10000 for g in mmdd_groups if "mmdd" in g}

            # DataFrames
            df_month = pd.DataFrame(list(month_stats.items()), columns=["Month", "Area_ha"])
            df_mmdd = pd.DataFrame(list(mmdd_stats.items()), columns=["MMDD", "Area_ha"])

            if df_month.empty or df_mmdd.empty:
                st.warning("No paddy pixels detected during this monitoring period.")
            else:
                # Month formatting
                df_month["Month"] = df_month["Month"].astype(int)
                df_month["Month_Name"] = df_month["Month"].apply(lambda x: calendar.month_name[int(x)])
                df_month["Seasonal_Order"] = df_month["Month"].apply(lambda x: seasonal_order.index(int(x)))
                df_month = df_month.sort_values("Seasonal_Order")
                df_month["Cumulative_Area_ha"] = df_month["Area_ha"].cumsum()

                # MMDD formatting
                df_mmdd = df_mmdd[df_mmdd["MMDD"] != 0]
                df_mmdd["Month_Day"] = df_mmdd["MMDD"].apply(lambda x: f"{str(int(x)).zfill(4)[:2]}-{str(int(x)).zfill(4)[2:]}")
                def consecutive_day_index(mmdd):
                    month = int(str(int(mmdd)).zfill(4)[:2])
                    day = int(str(int(mmdd)).zfill(4)[2:])
                    month_shifted = (month - season_start) % 12
                    return month_shifted * 31 + day
                df_mmdd["Seasonal_Index"] = df_mmdd["MMDD"].apply(consecutive_day_index)
                df_mmdd = df_mmdd.sort_values("Seasonal_Index")
                df_mmdd["Cumulative_Area_ha"] = df_mmdd["Area_ha"].cumsum()

                # Two columns, first row (bar charts)
                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    fig1, ax1 = plt.subplots(figsize=(6, 5))
                    ax1.bar(df_month["Month_Name"], df_month["Area_ha"], color="skyblue")
                    ax1.set_xlabel("Month")
                    ax1.set_ylabel("Area (ha)")
                    ax1.set_title("Paddy Area by Month")
                    plt.xticks(rotation=45)
                    st.pyplot(fig1)
                    plt.close(fig1)

                with col2:
                    fig2, ax2 = plt.subplots(figsize=(6, 5))
                    ax2.bar(df_mmdd["Month_Day"], df_mmdd["Area_ha"], color="lightgreen")
                    ax2.set_xlabel("Start Date (MM-DD)")
                    ax2.set_ylabel("Area (ha)")
                    ax2.set_title("Paddy Area by Start Date")
                    plt.xticks(rotation=45)
                    st.pyplot(fig2)
                    plt.close(fig2)

                with col3:
                    fig3, ax3 = plt.subplots(figsize=(5, 5))
                    wedges, texts, autotexts = ax3.pie(
                        df_month["Area_ha"],
                        startangle=90,
                        colors=plt.cm.tab20.colors,
                        autopct=lambda pct: f"{pct:.1f}%",
                        pctdistance=0.8,
                        wedgeprops=dict(width=0.5),
                    )
                    ax3.legend(
                        wedges, df_month["Month_Name"], title="Start Month",
                        loc="center left", bbox_to_anchor=(1, 0, 0.5, 1)
                    )
                    ax3.set_title("Paddy Area % by Month")
                    st.pyplot(fig3)
                    plt.close(fig3)

                with col4:
                    fig4, ax4 = plt.subplots(figsize=(5, 5))
                    cmap = plt.cm.viridis(np.linspace(0, 1, len(df_mmdd)))
                    wedges, texts, autotexts = ax4.pie(
                        df_mmdd["Area_ha"],
                        startangle=90,
                        colors=cmap,
                        autopct=lambda pct: f"{pct:.1f}%",
                        pctdistance=0.85,
                        wedgeprops=dict(width=0.5, edgecolor="w"),
                    )
                    ax4.legend(
                        wedges, df_mmdd["Month_Day"], title="Start Date (MM-DD)",
                        loc="center left", bbox_to_anchor=(1, 0, 0.5, 1)
                    )
                    ax4.set_title("Paddy Area % by Start Date")
                    st.pyplot(fig4)
                    plt.close(fig4)

                col1, col2 = st.columns(2)
                with col1:
                    x = np.arange(len(df_month))
                    fig_month, ax_month = plt.subplots(figsize=(9, 5))
                    ax_month.bar(x, df_month["Area_ha"], color='skyblue', width=0.5, label='Monthly Area (ha)')
                    ax_month.plot(x, df_month["Cumulative_Area_ha"],
                                color='darkgreen', marker='o', linewidth=2.5, label='Cumulative Area (ha)')
                    ax_month.fill_between(x, df_month["Cumulative_Area_ha"], color='green', alpha=0.15)

                    ax_month.set_xticks(x)
                    ax_month.set_xticklabels(df_month["Month_Name"], rotation=45)
                    ax_month.set_xlabel("Month")
                    ax_month.set_ylabel("Area (ha)")
                    ax_month.set_title("Monthly and Cumulative Paddy Area")
                    ax_month.grid(axis='y', linestyle='--', alpha=0.5)
                    ax_month.legend()

                    st.pyplot(fig_month, width='stretch')
                    plt.close(fig_month)

                with col2:
                    x = np.arange(len(df_mmdd))
                    fig_mmdd, ax_mmdd = plt.subplots(figsize=(10, 5))  # slightly wider
                    ax_mmdd.bar(x, df_mmdd["Area_ha"], color='skyblue', width=0.6, label='Dekadal Area (ha)')
                    ax_mmdd.plot(x, df_mmdd["Cumulative_Area_ha"],
                                color='darkgreen', marker='o', linewidth=2.5, label='Cumulative Area (ha)')
                    ax_mmdd.fill_between(x, df_mmdd["Cumulative_Area_ha"], color='green', alpha=0.15)

                    ax_mmdd.set_xticks(x)
                    ax_mmdd.set_xticklabels(df_mmdd["Month_Day"], rotation=45)
                    ax_mmdd.set_xlabel("Start Date (MM-DD)")
                    ax_mmdd.set_ylabel("Area (ha)")
                    ax_mmdd.set_title("Dekadal and Cumulative Paddy Area")
                    ax_mmdd.grid(axis='y', linestyle='--', alpha=0.5)
                    ax_mmdd.legend()

                    st.pyplot(fig_mmdd, width='stretch')
                    plt.close(fig_mmdd)

    else:
        st.markdown(
                "<span style='font-size:16px; color:gray;'>"
                "Performs near real-time monitoring for an active season. Define a time period to run the analysis."
                "</span>", unsafe_allow_html=True)
