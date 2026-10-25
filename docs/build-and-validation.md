# Build and validation

Use Python 3 in your normal environment with numpy, trimesh, manifold3d, scipy, matplotlib and Pillow. Install dependencies using your normal environment management; the scripts do not install or download anything. OpenSCAD must be on PATH, or pass `--openscad /path/to/openscad` (on Windows the CLI executable may be openscad.com). Optional `--deps /path/to/python-packages` adds an existing dependency directory; no machine-specific paths are embedded.

From the repository root:

```sh
python tools/verify_package.py
python tools/build_validate.py --regenerate
python tools/render_previews.py
```

`build_validate.py` checks the supplied STLs; `--regenerate` additionally exports all 12 variants from source into a temporary directory and compares closed solids by symmetric volume difference (<0.02 mm3) and bounds (0.002 mm tolerance). It never replaces the supplied STL bytes. Temporary exports are removed. OpenSCAD ASCII facet ordering may differ while the solid is equivalent. Without `--regenerate`, OpenSCAD is not needed for mesh checks.

Checks cover watertight single solids, winding, bounds, nominal printer envelope with brim, Z=0 placement, cavity and 0.30 mm normal rail clearance, continuous lid and assembled-case travel, rear stops, dovetail capture, optional screw-head envelope, shelf and neighbour clearance. Rack tests anchor the complete back to the first 2 mm above the bed and require every bay open upward. A deliberately inverted regression control must fail those geometric conditions.

Results are written to `reports/geometry-checks.json`; the mesh section plot is regenerated in `previews`. `render_previews.py` renders the actual supplied STLs through OpenSCAD; Pillow composes the public images. It does not use illustrative substitute geometry for the parts.

For an intentional package revision, update inventory only after reviewing files:

```sh
python tools/verify_package.py --write
python tools/verify_package.py
```

The manifest inventories every release file except itself and SHA256SUMS; SHA256SUMS also covers the manifest and excludes only itself. The verifier checks exact inventory, bytes, 12 STL hashes, local Markdown links, prohibited private identifiers/paths, image metadata and the unchanged licence hash. Git metadata and ignored Python environment/cache files are outside the release inventory. Render/build dependencies are not bundled.

See the committed [geometry result](../reports/geometry-checks.json). These are CAD and mesh checks only. Physical fit, quantity capacity, warping, stability and load performance remain untested. Direct printing is permitted; no preliminary test part is required.
