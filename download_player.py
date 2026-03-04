"""Download frontend bundle files from npm registry into static/"""
import urllib.request
import json
import tarfile
import io
import os


def download_npm_file(package, target_suffix, dest_path):
    """Download a specific file from an npm package tarball."""
    print(f"\n--- {package} ---")
    resp = urllib.request.urlopen(f"https://registry.npmjs.org/{package}/latest")
    data = json.loads(resp.read())
    tarball_url = data["dist"]["tarball"]
    print(f"Tarball: {tarball_url}")
    tgz_bytes = urllib.request.urlopen(tarball_url).read()
    print(f"Downloaded {len(tgz_bytes):,} bytes")

    with tarfile.open(fileobj=io.BytesIO(tgz_bytes), mode="r:gz") as tf:
        for member in tf.getmembers():
            if member.name.endswith(target_suffix):
                print(f"  Found: {member.name}")
                f = tf.extractfile(member)
                with open(dest_path, "wb") as out:
                    out.write(f.read())
                print(f"  Wrote: {dest_path}")
                return
    print(f"  WARNING: {target_suffix} not found in {package}")
    print("  Files in tarball:")
    with tarfile.open(fileobj=io.BytesIO(tgz_bytes), mode="r:gz") as tf:
        for member in tf.getmembers():
            print(f"    {member.name}")

os.makedirs("static", exist_ok=True)

download_npm_file("asciinema-player", "asciinema-player.min.js", "static/asciinema-player.min.js")
download_npm_file("asciinema-player", "asciinema-player.css",    "static/asciinema-player.css")
download_npm_file("lucide",           "umd/lucide.min.js",        "static/lucide.min.js")

print("\nAll done!")
