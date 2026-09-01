# Toolbox Parameters

For the complete ArcGIS-style reference, see [Create EAs](create_eas.md).

The `.pyt` file can be opened directly in ArcGIS Pro. Create EAs accepts administrative boundaries and their ID field, building points and their dwelling-count field, optional roads and rivers, dwelling thresholds, an initial building clustering distance, boundary alignment resolution, scoring weights, an output geodatabase, an output prefix, and an optional diagnostic report path.

Boundary Alignment Resolution controls the preferred allocation raster cell size and defaults to 5 meters. Smaller values can follow roads more closely but require more processing time and temporary storage. The tool automatically reduces the value when required to keep different candidate EA sources in separate raster cells.

ArcGIS Pro displays a description for the tool and dialog help for each parameter from `create_eas.CreateEAs.pyt.xml`. Parameter validation rejects missing required inputs, invalid threshold order, nonpositive distance or resolution values, negative scoring weights, and a zero total scoring weight. Execution also validates geometry types, selected fields, output collisions, projected coordinates, and Spatial Analyst availability.
