# Copyright 2018 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from collections import OrderedDict
import io
import tarfile
import unittest

from containerregistry.client.v2_2 import docker_image as v2_2_image


class MockImage(object):
  def __init__(self):
    self._fs_layers = OrderedDict()

  def add_layer(self, filenames):
    buf = io.BytesIO()
    with tarfile.open(mode='w:', fileobj=buf) as tf:
      for name in filenames:
        tarinfo = tarfile.TarInfo(name)
        if name.endswith("/"):
          tarinfo.type = tarfile.DIRTYPE
        tf.addfile(tarinfo)
    buf.seek(0)
    new_layer_id = str(len(self._fs_layers))
    self._fs_layers[new_layer_id] = buf.getvalue()

  def diff_ids(self):
    return reversed(self._fs_layers.keys())

  def uncompressed_layer(self, layer_id):
    return self._fs_layers[layer_id]


class TestExtract(unittest.TestCase):

  def _test_flatten(self, layer_filenames, expected_output_filenames):
    img = MockImage()
    for filenames in layer_filenames:
      img.add_layer(filenames)
    buf = io.BytesIO()
    with tarfile.open(mode='w:', fileobj=buf) as tar:
      v2_2_image.extract(img, tar)
    buf.seek(0)
    output_filenames = []
    with tarfile.open(mode='r', fileobj=buf) as tar:
      for tarinfo in tar:
        if tarinfo.isdir():
          output_filenames.append(tarinfo.name + "/")
        else:
          output_filenames.append(tarinfo.name)
    self.assertEqual(output_filenames, expected_output_filenames)

  def test_single_layer(self):
    self._test_flatten(
      [["/directory/", "/file"]],
      ["/directory/", "/file"]
    )

  def test_purely_additive_layers(self):
    self._test_flatten(
      [
        ["dir/", "dir/file1", "file"],
        ["dir/file2", "file2"]
      ],
      ["dir/file2", "file2", "dir/", "dir/file1", "file"]
    )

  def test_single_file_whiteout(self):
    self._test_flatten(
      [
        ["/foo"],
        ["/.wh.foo"]
      ],
      []
    )

  def test_parent_directory_whiteout(self):
    self._test_flatten(
      [
        ["/x/a/", "/x/b/", "/x/b/1"],
        ["/x/.wh.b"]
      ],
      ["/x/a/"]
    )

  def test_opaque_whiteout(self):
    # Examples from https://github.com/opencontainers/image-spec/blob/master/layer.md#whiteouts
    self._test_flatten(
      [
        ["a/", "a/b/", "a/b/c/", "a/b/c/bar"],
        ["a/", "a/.wh..wh..opq", "a/b/", "a/b/c/", "a/b/c/foo"],
      ],
      ["a/", "a/b/", "a/b/c/", "a/b/c/foo"],
    )

    self._test_flatten(
      [
        ["a/", "a/b/", "a/b/c/", "a/b/c/bar"],
        ["a/", "a/b/", "a/b/c/", "a/b/c/foo",  "a/.wh..wh..opq"],
      ],
      ["a/", "a/b/", "a/b/c/", "a/b/c/foo"],
    )


if __name__ == "__main__":
  unittest.main(verbosity=2)
