from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
import numpy as np
from .config import VoxelConfig
from . import path


def get_frustrum_transform(fx, fy, near_clip, far_clip, dtype=np.float32):
    depth_range = far_clip - near_clip
    p_22 = -(far_clip + near_clip) / depth_range
    p_23 = -2.0 * (far_clip * near_clip / depth_range)
    return np.array([
        [fx, 0, 0, 0],
        [0, fy, 0, 0],
        [0, 0, p_22, p_23],
        [0, 0, -1, 0]
    ], dtype=dtype)


def look_at(eye, center, world_up):
    # vector_degeneracy_cutoff = 1e-6
    dtype = eye.dtype
    forward = center - eye
    forward_norm = np.linalg.norm(forward, ord=2)
    forward /= forward_norm

    to_side = np.cross(forward, world_up)
    to_side_norm = np.linalg.norm(to_side, ord=2, keepdims=True)

    to_side /= to_side_norm
    cam_up = np.cross(to_side, forward)

    view_rotation = np.stack(
        [to_side, cam_up, -forward],
        axis=0)

    transform = np.empty((4, 4), dtype=dtype)
    transform[:3, :3] = view_rotation
    transform[:3, 3] = np.matmul(view_rotation, -eye)
    transform[3, :3] = 0
    transform[3, 3] = 1
    return transform


def get_frustrum_view_coordinates(
        shape, fx, fy, near_clip, far_clip, linear_z_world=True,
        dtype=np.float32):
    nx, ny, nz = shape
    # x = (2*(np.array(tuple(range(nx)), dtype=dtype) + 0.5) / nx - 1) / fx
    # y = (2*(np.array(tuple(range(ny)), dtype=dtype) + 0.5) / ny - 1) / fy
    # z = (np.array(tuple(range(ny)), dtype=dtype) + 0.5) / nz
    # z *= (far_clip - near_clip)
    # z += near_clip
    # z *= -1
    #
    # x *= -1  # because hax?
    #
    # X, Y = np.meshgrid(x, y, indexing='ij')
    # X = np.expand_dims(X, axis=-1)
    # Y = np.expand_dims(Y, axis=-1)
    # Z = np.expand_dims(np.expand_dims(z, 0), 0)
    # X = X*Z
    # Y = Y*Z
    # Z = np.tile(Z, (nx, ny, 1))
    # xyzh = np.stack((X, Y, Z, np.ones_like(X)), axis=-1)

    frustrum_transform = get_frustrum_transform(fx, fy, near_clip, far_clip)
    x = 2*(np.array(tuple(range(nx)), dtype=dtype) + 0.5) / nx - 1
    y = 2*(np.array(tuple(range(ny)), dtype=dtype) + 0.5) / ny - 1
    y *= -1  # fixes left/right coordinate frame issues?
    if linear_z_world:
        ze = (np.array(tuple(range(ny)), dtype=dtype) + 0.5) / nz
        ze *= (far_clip - near_clip)
        ze += near_clip
        ze *= -1
        zero = np.zeros_like(ze)
        one = np.ones_like(ze)
        zeht = np.stack([zero, zero, ze, one], axis=0)
        zh = np.matmul(frustrum_transform, zeht).T
        z = zh[..., 2] / zh[..., 3]
    else:
        z = 2*(np.array(tuple(range(ny)), dtype=dtype) + 0.5) / nz - 1
    X, Y, Z = np.meshgrid(x, y, z, indexing='ij')
    xyzh = np.stack([X, Y, Z, np.ones((nx, ny, nz), dtype=dtype)], axis=0)
    xyzh = np.reshape(xyzh, (4, -1))
    xyzh = np.linalg.solve(frustrum_transform, xyzh)

    return xyzh


# def vis(xyz):
#     from mayavi import mlab
#     from sdf_renderer.vis import vis_axes
#     from util3d.mayavi_vis import vis_point_cloud
#     vis_point_cloud(xyz, scale_factor=0.2)
#     vis_axes()
#     mlab.show()
#     exit()


def dehomogenize(xyzh):
    if xyzh.shape[0] != 4:
        raise ValueError(
            'xyzh must have leading dimension 4, got %d' % xyzh.shape[0])
    return xyzh[:3] / xyzh[3:]


def get_world_to_view_transform(eye_z, theta, dtype=np.float32):
    k = np.array([0, 0, 1], dtype=dtype)
    eye = np.array([-np.sin(theta), np.cos(theta), eye_z], dtype=dtype)
    center = np.array([0, 0, 0], dtype=dtype)
    return look_at(eye, center, k)


def get_frstrum_grid_world_coords(
        shape, fx, fy, near_clip, far_clip, eye_z, theta, linear_z_world=True,
        dtype=np.float32):
    shape = tuple(shape)
    xyzh = get_frustrum_view_coordinates(
            shape, fx, fy, near_clip, far_clip, linear_z_world=linear_z_world,
            dtype=dtype)

    view_transform = get_world_to_view_transform(eye_z, theta, dtype)

    xyzh = np.linalg.solve(view_transform, xyzh)
    return xyzh


# def get_frstrum_grid_world_coords(
#         shape, fx, fy, near_clip, far_clip, eye_z, theta,
#         linear_z_world=True, dtype=np.float32):
#     """Get frustrum grid points in world coordinates."""
#
#     frustrum_transform = get_frustrum_transform(fx, fy, near_clip, far_clip)
#
#     nx, ny, nz = shape
#     x = 2*(np.array(tuple(range(nx)), dtype=dtype) + 0.5) / nx - 1
#     y = 2*(np.array(tuple(range(ny)), dtype=dtype) + 0.5) / ny - 1
#     y *= -1  # fixes left/right coordinate frame issues?
#     if linear_z_world:
#         ze = (np.array(tuple(range(ny)), dtype=dtype) + 0.5) / nz
#         ze *= (far_clip - near_clip)
#         ze += near_clip
#         ze *= -1
#         zero = np.zeros_like(ze)
#         one = np.ones_like(ze)
#         zeht = np.stack([zero, zero, ze, one], axis=0)
#         zh = np.matmul(frustrum_transform, zeht).T
#         z = zh[..., 2] / zh[..., 3]
#     else:
#         z = 2*(np.array(tuple(range(ny)), dtype=dtype) + 0.5) / nz - 1
#     X, Y, Z = np.meshgrid(x, y, z, indexing='ij')
#     xyzh = np.stack([X, Y, Z, np.ones((nx, ny, nz), dtype=dtype)], axis=-1)
#
#     k = np.array([0, 0, 1], dtype=dtype)
#     eye = np.array([-np.sin(theta), np.cos(theta), eye_z], dtype=dtype)
#     center = np.array([0, 0, 0], dtype=dtype)
#     view_transform = look_at(eye, center, k)
#     combined_transform = np.matmul(frustrum_transform, view_transform)
#
#     xyzh = np.reshape(xyzh, (-1, 4))
#     xyzh_world = np.linalg.solve(combined_transform, xyzh.T).T
#     xyzh_world = np.reshape(xyzh_world, (nx, ny, nz, 4))
#     xyz_world = xyzh_world[..., :3] / xyzh_world[..., 3:]
#
#     return xyz_world


class FrustrumVoxelConfig(VoxelConfig):
    def __init__(
            self, base_voxel_config, render_config, view_index, shape):
        self._base_config = base_voxel_config
        self._render_config = render_config
        self._view_index = view_index
        self._theta = np.deg2rad(render_config.view_angle(view_index))
        scale = render_config.scale
        if scale is None:
            scale = 1
        self._eye_z = 0.6
        D = np.sqrt(self._eye_z**2 + 1)
        self._near_clip = D - 0.5*scale
        self._far_clip = self._near_clip + scale
        self._shape = shape
        self._view_index = view_index
        self._shape = tuple(shape)
        assert(
            len(self._shape) == 3 and
            all(isinstance(s, int) for s in self._shape))
        self._voxel_id = '%s_%s%d_%s' % (
                base_voxel_config.voxel_id, render_config.config_id,
                view_index, '-'.join(str(s) for s in shape))
        h, w = render_config.shape
        # fx = 35 / 32
        fx = 35 / (32 / 2)
        fy = fx * h / w

        self._fx = fx
        self._fy = fy

    @property
    def shape(self):
        return self._shape

    @property
    def voxel_id(self):
        return self._voxel_id

    @property
    def root_dir(self):
        subdir = '%s_%s_%d-%d-%d' % ((
            self._base_config.voxel_id, self._render_config.config_id,
            ) + self.shape)
        dir = os.path.join(
            path.data_dir, 'rotated', subdir, 'v%02d' % self._view_index)
        if not os.path.isdir(dir):
            os.makedirs(dir)
        return dir

    def transformer(self):
        world_coords = get_frstrum_grid_world_coords(
                 self._shape, self._fx, self._fy, self._near_clip,
                 self._far_clip, self._eye_z, self._theta, linear_z_world=True)
        world_coords = dehomogenize(world_coords)
        world_coords = np.reshape(world_coords, (3,) + self._shape)
        voxel_dim = self._base_config.voxel_dim
        voxel_coords = (world_coords + 0.5) * voxel_dim
        voxel_coords = np.floor(voxel_coords).astype(np.int32)
        inside = np.all(
            np.logical_and(voxel_coords >= 0, voxel_coords < voxel_dim),
            axis=0)
        outside = np.logical_not(inside)
        voxel_coords[:, outside] = 0

        coords_flat = np.reshape(voxel_coords, (3, -1))
        i, j, k = coords_flat
        shape = self.shape

        def f(voxels):
            # data = voxels.gather((i, j, k))
            data = voxels.gather((i, j, k))
            # data = voxels.gather((i, j, k), fix_coords=True)
            # data = voxels.dense_data()[i, j, k]
            data = np.reshape(data, shape)
            data[outside] = 0
            return data

        return f

    def create_voxel_data(self, cat_id, example_ids=None, overwrite=False):
        from progress.bar import IncrementalBar
        from util3d.voxel.binvox import DenseVoxels
        transformer = self.transformer()
        with self._base_config.get_dataset(cat_id, 'r') as base:
            if example_ids is None:
                example_ids = tuple(base.keys())
            bar = IncrementalBar(max=len(example_ids))
            for example_id in example_ids:
                bar.next()
                path = self.get_binvox_path(cat_id, example_id)
                folder = os.path.dirname(path)
                if not os.path.isdir(folder):
                    os.makedirs(folder)
                if os.path.isfile(path):
                    if overwrite:
                        os.remove(path)
                    else:
                        continue
                out = DenseVoxels(transformer(base[example_id]))
                out.save(path)
            bar.finish()