SELECT 7 resolution,count(*) cells,sum(n.area_m2)/1e6 area_km2,
      min(n.iop) min_v2,max(n.iop) max_v2,sum(n.iop*n.area_m2)/sum(n.area_m2) area_mean_v2,
      avg(o.iop) mean_v1,avg(n.iop) mean_v2,corr(o.iop,n.iop) correlation,
      count(*) FILTER(WHERE n.fraction_urban+n.fraction_hard>=.5) built_or_hard_cells,
      avg(n.iop) FILTER(WHERE n.fraction_urban>=.5) urban_v2,
      avg(o.iop) FILTER(WHERE n.fraction_urban>=.5) urban_v1,
      count(*) FILTER(WHERE n.barrier_present) barrier_cells,
      sum(n.unknown_fraction*n.area_m2)/sum(n.area_m2) unknown_area_fraction
      FROM grid.iop_v2_r7 n JOIN grid.iop_r7 o USING(h3_id) UNION ALL SELECT 8 resolution,count(*) cells,sum(n.area_m2)/1e6 area_km2,
      min(n.iop) min_v2,max(n.iop) max_v2,sum(n.iop*n.area_m2)/sum(n.area_m2) area_mean_v2,
      avg(o.iop) mean_v1,avg(n.iop) mean_v2,corr(o.iop,n.iop) correlation,
      count(*) FILTER(WHERE n.fraction_urban+n.fraction_hard>=.5) built_or_hard_cells,
      avg(n.iop) FILTER(WHERE n.fraction_urban>=.5) urban_v2,
      avg(o.iop) FILTER(WHERE n.fraction_urban>=.5) urban_v1,
      count(*) FILTER(WHERE n.barrier_present) barrier_cells,
      sum(n.unknown_fraction*n.area_m2)/sum(n.area_m2) unknown_area_fraction
      FROM grid.iop_v2_r8 n JOIN grid.iop_r8 o USING(h3_id) UNION ALL SELECT 9 resolution,count(*) cells,sum(n.area_m2)/1e6 area_km2,
      min(n.iop) min_v2,max(n.iop) max_v2,sum(n.iop*n.area_m2)/sum(n.area_m2) area_mean_v2,
      avg(o.iop) mean_v1,avg(n.iop) mean_v2,corr(o.iop,n.iop) correlation,
      count(*) FILTER(WHERE n.fraction_urban+n.fraction_hard>=.5) built_or_hard_cells,
      avg(n.iop) FILTER(WHERE n.fraction_urban>=.5) urban_v2,
      avg(o.iop) FILTER(WHERE n.fraction_urban>=.5) urban_v1,
      count(*) FILTER(WHERE n.barrier_present) barrier_cells,
      sum(n.unknown_fraction*n.area_m2)/sum(n.area_m2) unknown_area_fraction
      FROM grid.iop_v2_r9 n JOIN grid.iop_r9 o USING(h3_id);
SELECT 7 resolution,ST_Area(ST_SymDifference(g.geom,p.geom)) missing_or_extra_m2
      FROM (SELECT ST_UnaryUnion(ST_Collect(ST_Transform(geom,2180))) geom FROM grid.iop_v2_r7) g
      CROSS JOIN (SELECT ST_UnaryUnion(ST_Collect(ST_Transform(geom,2180))) geom FROM public.powiat) p UNION ALL SELECT 8 resolution,ST_Area(ST_SymDifference(g.geom,p.geom)) missing_or_extra_m2
      FROM (SELECT ST_UnaryUnion(ST_Collect(ST_Transform(geom,2180))) geom FROM grid.iop_v2_r8) g
      CROSS JOIN (SELECT ST_UnaryUnion(ST_Collect(ST_Transform(geom,2180))) geom FROM public.powiat) p UNION ALL SELECT 9 resolution,ST_Area(ST_SymDifference(g.geom,p.geom)) missing_or_extra_m2
      FROM (SELECT ST_UnaryUnion(ST_Collect(ST_Transform(geom,2180))) geom FROM grid.iop_v2_r9) g
      CROSS JOIN (SELECT ST_UnaryUnion(ST_Collect(ST_Transform(geom,2180))) geom FROM public.powiat) p;