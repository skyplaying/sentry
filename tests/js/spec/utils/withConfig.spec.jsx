import React from 'react';

import {mountWithTheme} from 'sentry-test/enzyme';

import ConfigStore from 'app/stores/configStore';
import withConfig from 'app/utils/withConfig';

describe('withConfig HoC', function () {
  it('adds config prop', async function () {
    ConfigStore.init();
    const MyComponent = () => null;
    const Container = withConfig(MyComponent);
    const wrapper = mountWithTheme(<Container />);
    expect(wrapper.find('MyComponent').prop('config')).toEqual({});
    ConfigStore.set('user', 'foo');
    wrapper.update();
    expect(wrapper.find('MyComponent').prop('config')).toEqual({user: 'foo'});
  });
});
