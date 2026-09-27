"""A vendored wheel as a py_library: unpack it (a wheel is a zip of site-packages) and glob it.

Relocatable by construction: a wheel carries real files, not pointers at a host checkout, so the
sandbox sees exactly the vendored bytes. The label is the input, so re-vendoring invalidates it.
"""

def _impl(rctx):
    # extract() infers the format from the extension, and .whl is not one it knows: it is a zip.
    rctx.symlink(rctx.path(rctx.attr.wheel), "wheel.zip")
    rctx.extract("wheel.zip", output = "site-packages")
    rctx.delete("wheel.zip")
    rctx.file("BUILD.bazel", """load("@rules_python//python:defs.bzl", "py_library")
py_library(
    name = "lib",
    srcs = glob(["site-packages/**/*.py"]),
    data = glob(["site-packages/**/*"], exclude = ["**/*.py", "*/*.dist-info/RECORD"]),
    imports = ["site-packages"],
    visibility = ["//visibility:public"],
)

# nemik:W96: the same shape pip.parse gives its wheels, so bazel/venv.bzl can install this one too.
filegroup(
    name = "extracted_whl_files",
    srcs = glob(["site-packages/**/*"]),
    visibility = ["//visibility:public"],
)
""")

vendored_wheel = repository_rule(
    implementation = _impl,
    attrs = {"wheel": attr.label(allow_single_file = [".whl"])},
)
