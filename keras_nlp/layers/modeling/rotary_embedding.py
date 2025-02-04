# Copyright 2023 The KerasNLP Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from keras_nlp.api_export import keras_nlp_export
from keras_nlp.backend import keras
from keras_nlp.backend import ops


@keras_nlp_export("keras_nlp.layers.RotaryEmbedding")
class RotaryEmbedding(keras.layers.Layer):
    """Rotary positional encoding layer.

    This layer encodes absolute positional information with a rotation
    matrix. It calculates the rotary encoding with a mix of sine and
    cosine functions with geometrically increasing wavelengths.
    Defined and formulated in [RoFormer: Enhanced Transformer with Rotary Position Embedding](https://arxiv.org/abs/2104.09864v4).
    The input must be a tensor with shape a sequence dimension and a feature
    dimension. Typically, this will either an input with shape
    `(batch_size, sequence_length, feature_length)` or
    `(batch_size, sequence_length, num_heads, feature_length)`.
    This layer will return a new tensor with the rotary embedding applied to
    the input tensor.

    Args:
        max_wavelength: int. The maximum angular wavelength of the sine/cosine
            curves.
        scaling_factor: float. The scaling factor used to scale frequency range.
        sequence_axis: int. Sequence axis in the input tensor.
        feature_axis: int. Feature axis in the input tensor.

    Examples:

    ```python
    batch_size = 16
    feature_length = 18
    sequence_length = 256
    num_heads = 8

    # No multi-head dimension.
    tensor = tf.ones((batch_size, sequence_length, feature_length))
    rot_emb_layer = RotaryEmbedding()
    tensor_rot = rot_emb_layer(tensor)

    # With multi-head dimension.
    tensor = tf.ones((batch_size, sequence_length, num_heads, feature_length))
    tensor_rot = rot_emb_layer(tensor)
    ```

    References:
     - [RoFormer: Enhanced Transformer with Rotary Position Embedding](https://arxiv.org/abs/2104.09864v4)
    """

    def __init__(
        self,
        max_wavelength=10000,
        scaling_factor=1.0,
        sequence_axis=1,
        feature_axis=-1,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.max_wavelength = max_wavelength
        self.sequence_axis = sequence_axis
        self.feature_axis = feature_axis
        self.scaling_factor = scaling_factor

    def call(self, inputs):
        rotary_dim = ops.shape(inputs)[-1]
        cos_emb, sin_emb = self._compute_cos_sin_embedding(inputs, rotary_dim)
        return self._apply_rotary_pos_emb(inputs, cos_emb, sin_emb)

    def _apply_rotary_pos_emb(self, tensor, cos_emb, sin_emb):
        x1, x2 = ops.split(tensor, 2, axis=self.feature_axis)
        half_rot_tensor = ops.concatenate((-x2, x1), axis=self.feature_axis)
        return (tensor * cos_emb) + (half_rot_tensor * sin_emb)

    def _compute_cos_sin_embedding(self, x, rotary_dim):
        freq_range = ops.arange(0, rotary_dim, 2, dtype="float32")
        freq_range = ops.cast(freq_range, self.compute_dtype)
        freq_range = freq_range / ops.cast(
            self.scaling_factor, self.compute_dtype
        )
        inverse_freq = 1.0 / (
            self.max_wavelength
            ** (freq_range / ops.cast(rotary_dim, self.compute_dtype))
        )
        seq_len = ops.shape(x)[self.sequence_axis]
        tensor = ops.arange(seq_len, dtype="float32")
        tensor = ops.cast(tensor, dtype=inverse_freq.dtype)
        freq = ops.einsum("i, j -> ij", tensor, inverse_freq)
        embedding = ops.concatenate((freq, freq), axis=self.feature_axis)

        def get_axis(axis):
            return axis if axis > 0 else len(x.shape) + axis

        feature_axis = get_axis(self.feature_axis)
        sequence_axis = get_axis(self.sequence_axis)

        for axis in range(len(x.shape)):
            if axis != sequence_axis and axis != feature_axis:
                embedding = ops.expand_dims(embedding, axis)

        return ops.cos(embedding), ops.sin(embedding)

    def get_config(self):
        config = super().get_config()
        config.update(
            {
                "max_wavelength": self.max_wavelength,
                "scaling_factor": self.scaling_factor,
                "sequence_axis": self.sequence_axis,
                "feature_axis": self.feature_axis,
            }
        )
        return config

    def compute_output_shape(self, input_shape):
        return input_shape
