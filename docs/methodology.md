# Methodology

The planned workflow reads one point per building, carries its dwelling count, assigns each point to one administrative polygon, and builds a spatial neighborhood graph. Candidate EAs grow from deterministic seeds through valid neighboring buildings. A merge is rejected when administrative IDs differ, a hard barrier is crossed, the candidate is disconnected, or the maximum dwelling threshold is exceeded.

Merge scoring normalizes dwelling target deviation, building-count balance, and distance before applying runtime weights. Shared boundary is a reward. Threshold status is separate from review lifecycle status so a candidate can be undersized or oversized while still remaining a proposal for human review.

After building assignments are fixed, each administrative unit is partitioned with Spatial Analyst distance allocation. Assigned buildings are integer-valued sources for their candidate EA. Road cells add traversal cost according to road class, with major roads receiving the strongest influence, causing allocation fronts to prefer meeting along roads. The preferred cell size is configurable and defaults to 5 meters; it is reduced automatically when necessary to preserve distinct candidate sources. The allocation raster is converted to multipart polygons and clipped to the exact administrative geometry. The resulting candidate polygons do not overlap and collectively fill every administrative unit that contains assigned buildings.

ArcPy preprocessing, road and river classification, geometry generation, effort aggregation, cleanup, splitting, update lineage, and toolbox parameters will be documented as they are implemented.
