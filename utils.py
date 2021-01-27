import time

def find_first_change(init_val, lower_bound, upper_bound, func):
    # binary search to find the first change of descrete function func
    while upper_bound - lower_bound > 1:
        mid = (lower_bound + upper_bound) // 2
        val = func(mid)
        if val == init_val:
            lower_bound = mid
        else:
            upper_bound = mid

    return upper_bound

def interp_search(target, x_range, y_range, func, mode='upper'):
    # discrete interpolation search: assuming monotonic function y of x, find value of x
    # which yields the closest value of y to the target
    x_bounds, y_bounds = list(x_range), list(y_range)
    eval_count = 0
    while x_bounds[1] - x_bounds[0] > 1:
        proportion = (target - y_bounds[0]) / (y_bounds[1] - y_bounds[0])
        diff = max(1, round(proportion * (x_bounds[1] - x_bounds[0])))
        x_estimate = min(x_bounds[0] + diff, x_bounds[1] - 1)
        y_estimate = func(x_estimate)
        eval_count += 1
        if y_estimate == target:
            return x_estimate, 0, eval_count
        elif y_estimate < target:
            x_bounds[0], y_bounds[0] = x_estimate, y_estimate
        elif y_estimate > target:
            x_bounds[1], y_bounds[1] = x_estimate, y_estimate

    if mode == 'closest':
        if y_bounds[1] - target >= target - y_bounds[0]:
            return x_bounds[0], y_bounds[0] - target, eval_count
        else:
            return x_bounds[1], y_bounds[1] - target, eval_count
    elif mode == 'lower':
        return x_bounds[0], y_bounds[0] - target, eval_count
    else:
        return x_bounds[1], y_bounds[1] - target, eval_count

def progress_string(current_iteration, total_iterations, start_time):
    # write a progress statement which will be overwritten afterwards
    elapsed = time.strftime("%H:%M:%S", time.gmtime(time.time() - start_time))
    return (f"{current_iteration+1} of {total_iterations} "
            f"({100*(current_iteration+1)/total_iterations:.2f}% complete) in {elapsed}")
